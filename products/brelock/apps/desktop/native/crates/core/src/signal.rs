use crate::config::AppConfig;
use serde::Serialize;
use std::collections::VecDeque;

const BUCKET_S: f64 = 0.25;
// CoreBluetooth may coalesce advertisements into uneven bursts. A three-second
// median window keeps the signal usable across those gaps without treating a
// stale packet as fresh telemetry.
const MEDIAN_S: f64 = 3.0;
const EMA_TAU_S: f64 = 0.8;
const TREND_S: f64 = 3.0;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TrendQuality {
    WarmingUp,
    Gaps,
    NoClearTrend,
    Valid,
    Stale,
}

#[derive(Debug, Clone, Serialize)]
pub struct TrendSnapshot {
    pub quality: TrendQuality,
    pub points: usize,
    pub span_s: f64,
    pub coverage: f64,
    pub slope_db_s: Option<f64>,
    pub r_squared: Option<f64>,
}

#[derive(Debug, Default)]
pub struct SignalFilter {
    pending_bucket: Option<u64>,
    samples: VecDeque<f64>,
    bins: VecDeque<(f64, f64)>,
    points: VecDeque<(f64, f64)>,
    ema: Option<(f64, f64)>,
}

fn median(values: impl Iterator<Item = f64>) -> f64 {
    let mut values: Vec<_> = values.collect();
    values.sort_by(f64::total_cmp);
    let middle = values.len() / 2;
    if values.len().is_multiple_of(2) {
        (values[middle - 1] + values[middle]) / 2.0
    } else {
        values[middle]
    }
}

impl SignalFilter {
    pub fn add(&mut self, at: f64, rssi: f64) {
        self.advance(at);
        self.pending_bucket = Some((at / BUCKET_S).floor() as u64);
        if self.samples.len() == 64 {
            self.samples.pop_front();
        }
        self.samples.push_back(rssi);
    }

    pub fn advance(&mut self, at: f64) {
        if let Some(bucket) = self.pending_bucket {
            let end = (bucket as f64 + 1.0) * BUCKET_S;
            if at >= end {
                self.finish(end);
                self.pending_bucket = None;
                self.samples.clear();
            }
        }
        while self
            .points
            .front()
            .is_some_and(|point| point.0 < at - TREND_S)
        {
            self.points.pop_front();
        }
    }

    fn finish(&mut self, at: f64) {
        if self.samples.is_empty() {
            return;
        }
        self.bins
            .push_back((at, median(self.samples.iter().copied())));
        while self
            .bins
            .front()
            .is_some_and(|point| point.0 <= at - MEDIAN_S)
        {
            self.bins.pop_front();
        }
        if self.bins.len() < 2 {
            return;
        }
        let value = median(self.bins.iter().map(|point| point.1));
        let filtered = self.ema.map_or(value, |(previous_at, previous)| {
            let alpha = -(-(at - previous_at) / EMA_TAU_S).exp_m1();
            previous + alpha * (value - previous)
        });
        self.ema = Some((at, filtered));
        self.points.push_back((at, filtered));
    }

    pub fn filtered(&self) -> Option<f64> {
        self.ema.map(|point| point.1)
    }

    pub fn trend(&self, fresh: bool) -> TrendSnapshot {
        let mut result = TrendSnapshot {
            quality: if fresh {
                TrendQuality::WarmingUp
            } else {
                TrendQuality::Stale
            },
            points: self.points.len(),
            span_s: 0.0,
            coverage: 0.0,
            slope_db_s: None,
            r_squared: None,
        };
        let (Some(first), Some(last)) = (self.points.front(), self.points.back()) else {
            return result;
        };
        result.span_s = last.0 - first.0;
        result.coverage = (self.points.len() as f64 / (TREND_S / BUCKET_S)).min(1.0);
        if !fresh || self.points.len() < 6 || result.span_s < 2.4 - 1e-9 {
            return result;
        }
        if result.coverage < 0.8 {
            result.quality = TrendQuality::Gaps;
            return result;
        }
        let count = self.points.len() as f64;
        let x_mean = self
            .points
            .iter()
            .map(|point| point.0 - first.0)
            .sum::<f64>()
            / count;
        let y_mean = self.points.iter().map(|point| point.1).sum::<f64>() / count;
        let sxx = self
            .points
            .iter()
            .map(|point| (point.0 - first.0 - x_mean).powi(2))
            .sum::<f64>();
        let syy = self
            .points
            .iter()
            .map(|point| (point.1 - y_mean).powi(2))
            .sum::<f64>();
        let slope = self
            .points
            .iter()
            .map(|point| (point.0 - first.0 - x_mean) * (point.1 - y_mean))
            .sum::<f64>()
            / sxx;
        let residual = self
            .points
            .iter()
            .map(|point| (point.1 - y_mean - slope * (point.0 - first.0 - x_mean)).powi(2))
            .sum::<f64>();
        result.slope_db_s = Some(slope);
        result.r_squared = (syy > 1e-12).then(|| (1.0 - residual / syy).clamp(0.0, 1.0));
        result.quality = if result.r_squared.is_some_and(|r2| r2 >= 0.5) {
            TrendQuality::Valid
        } else {
            TrendQuality::NoClearTrend
        };
        result
    }
}

pub fn estimate_distance(rssi: f64, config: &AppConfig) -> Option<f64> {
    let distance =
        10.0_f64.powf((config.reference_rssi_dbm - rssi) / (10.0 * config.path_loss_exponent));
    (distance.is_finite() && distance > 0.0).then_some(distance)
}

/// Derivative of the RSSI distance model, NOT integrated linear IMU velocity.
pub fn estimate_radial_speed(
    distance: f64,
    trend: &TrendSnapshot,
    config: &AppConfig,
) -> Option<f64> {
    if trend.quality != TrendQuality::Valid {
        return None;
    }
    let speed = -std::f64::consts::LN_10 * distance * trend.slope_db_s?
        / (10.0 * config.path_loss_exponent);
    speed.is_finite().then_some(speed)
}
