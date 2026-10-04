//! Collect real RSSI observations AFTER the user marks the departure boundary.
use brelock_core::{AppConfig, config::ConfigError};
use serde::Serialize;
use std::collections::VecDeque;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CalibrationReading {
    pub t_s: f64,
    pub rssi_dbm: f64,
}
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct CalibrationResult {
    pub median_dbm: f64,
    pub threshold_dbm: f64,
    pub mad_db: f64,
    pub margin_db: f64,
    pub sample_count: usize,
}

impl CalibrationResult {
    /// Fit the distance scale to the same stationary samples as the lock boundary.
    /// One known distance identifies the reference RSSI; the exponent stays as configured.
    pub fn calibrated_config(
        self,
        current: &AppConfig,
        distance_m: f64,
    ) -> Result<AppConfig, ConfigError> {
        let mut config = current.clone();
        config.calibration_distance_m = distance_m;
        config.validate()?;
        config.reference_rssi_dbm =
            self.median_dbm + 10.0 * config.path_loss_exponent * distance_m.log10();
        config.departure_threshold_dbm = Some(self.threshold_dbm);
        config.validate()?;
        Ok(config)
    }
}

// Connected RSSI cadence varies with the OS and radio scheduling. Require real
// time coverage and freshness, rather than an advertising-rate sample count.
pub const CALIBRATION_MIN_SAMPLES: usize = 8;
pub const CALIBRATION_SETTLE_S: f64 = 2.0;
pub const CALIBRATION_TARGET_S: f64 = 10.0;
pub const CALIBRATION_WINDOW_S: f64 = 20.0;
pub const CALIBRATION_TIMEOUT_S: f64 = 35.0;
const MIN_SPAN_S: f64 = 8.0;
const MAX_SAMPLE_AGE_S: f64 = 2.5;
const MAX_GAP_S: f64 = 3.5;
const MAX_MAD_DB: f64 = 8.0;
const MAX_DRIFT_DB: f64 = 8.0;

#[derive(Debug)]
pub struct CalibrationMeasurement {
    started_at_s: f64,
    require_boundary_range: bool,
    readings: VecDeque<CalibrationReading>,
    percent: u8,
}
#[derive(Debug)]
pub struct CalibrationProgress {
    pub sample_count: usize,
    pub elapsed_s: f64,
    pub percent: u8,
    pub message: &'static str,
    pub result: Option<CalibrationResult>,
    pub timed_out: bool,
}

impl CalibrationMeasurement {
    pub fn new(started_at_s: f64) -> Self {
        Self {
            started_at_s,
            require_boundary_range: true,
            readings: VecDeque::new(),
            percent: 0,
        }
    }
    /// Near points only fit the radio model; their RSSI may be stronger than
    /// the accepted departure boundary. Only the final point sets that boundary.
    pub fn model_point(started_at_s: f64) -> Self {
        Self {
            require_boundary_range: false,
            ..Self::new(started_at_s)
        }
    }
    pub fn observe(&mut self, reading: CalibrationReading) {
        if !reading.t_s.is_finite() || !reading.rssi_dbm.is_finite()
            || !(-127.0..=-1.0).contains(&reading.rssi_dbm)
            || reading.t_s < self.started_at_s + CALIBRATION_SETTLE_S
            // Cap sample weight at 5 Hz. Duplicate timestamps and bursts must
            // not masquerade as time coverage or dominate the boundary median.
            || self.readings.back().is_some_and(|last| reading.t_s - last.t_s < 0.2)
        {
            return;
        }
        self.readings.push_back(reading);
        self.prune(reading.t_s);
    }
    fn prune(&mut self, now_s: f64) {
        while self
            .readings
            .front()
            .is_some_and(|r| r.t_s < now_s - CALIBRATION_WINDOW_S)
        {
            self.readings.pop_front();
        }
    }
    pub fn poll(&mut self, now_s: f64) -> CalibrationProgress {
        self.prune(now_s);
        let elapsed_s = (now_s - self.started_at_s).max(0.0);
        let sampling_s = (elapsed_s - CALIBRATION_SETTLE_S).max(0.0);
        let values: Vec<_> = self.readings.iter().copied().collect();
        let (result, message) = if sampling_s < CALIBRATION_TARGET_S {
            (
                None,
                if elapsed_s < CALIBRATION_SETTLE_S {
                    "Ustaw brelok w zwykłej pozycji noszenia. Pomijam ruch po dotknięciu."
                } else {
                    "Zbieram pomiar. Pozostań w miejscu; zapis nastąpi automatycznie."
                },
            )
        } else if self
            .readings
            .back()
            .is_none_or(|r| now_s - r.t_s > MAX_SAMPLE_AGE_S)
        {
            (
                None,
                "Czekam na świeży odczyt RSSI. Sprawdź połączenie breloka.",
            )
        } else {
            match calibrate_point(&values, self.require_boundary_range) {
                Ok(result) => (Some(result), "Pomiar gotowy."),
                Err(message) => (None, message),
            }
        };
        let candidate = ((sampling_s / CALIBRATION_TARGET_S)
            .min(values.len() as f64 / CALIBRATION_MIN_SAMPLES as f64)
            .clamp(0.0, 1.0)
            * 95.0) as u8;
        self.percent = if result.is_some() {
            100
        } else {
            self.percent.max(candidate)
        };
        CalibrationProgress {
            sample_count: values.len(),
            elapsed_s,
            percent: self.percent,
            message,
            result,
            timed_out: result.is_none() && elapsed_s >= CALIBRATION_TIMEOUT_S,
        }
    }
}
#[cfg(test)]
fn calibrate_departure_threshold(
    values: &[CalibrationReading],
) -> Result<CalibrationResult, &'static str> {
    calibrate_point(values, true)
}
fn calibrate_point(
    values: &[CalibrationReading],
    require_boundary_range: bool,
) -> Result<CalibrationResult, &'static str> {
    if values.len() < CALIBRATION_MIN_SAMPLES {
        return Err("Odczyty RSSI są rzadsze. Zbieram dłużej; nie dotykaj ponownie.");
    }
    if values.last().unwrap().t_s - values.first().unwrap().t_s < MIN_SPAN_S {
        return Err("Potrzebuję dłuższego pomiaru w jednym miejscu.");
    }
    if values
        .windows(2)
        .any(|pair| pair[1].t_s - pair[0].t_s > MAX_GAP_S)
    {
        return Err("W pomiarze była przerwa BLE. Czekam na ciągły odbiór.");
    }
    let mut rssi: Vec<_> = values.iter().map(|r| r.rssi_dbm).collect();
    let third = (rssi.len() / 3).max(1);
    let early = median(&mut rssi[..third].to_vec());
    let late = median(&mut rssi[rssi.len() - third..].to_vec());
    if (early - late).abs() > MAX_DRIFT_DB {
        return Err("Poziom sygnału nadal się zmienia. Zatrzymaj się i zachowaj pozycję breloka.");
    }
    let median_dbm = median(&mut rssi);
    let mut deviations: Vec<_> = rssi.iter().map(|v| (v - median_dbm).abs()).collect();
    let mad_db = median(&mut deviations);
    let lower = rssi[(rssi.len() - 1) / 4];
    let upper = rssi[(rssi.len() - 1) * 3 / 4];
    // MAD can be zero for quantized or bimodal RSSI with a narrow majority.
    let dispersion_db = mad_db.max((upper - lower) / 2.0);
    if dispersion_db > MAX_MAD_DB {
        return Err("Duże wahania sygnału. Trzymaj brelok w jednej pozycji; ponawiam pomiar.");
    }
    // Normal body/radio noise should not make calibration impossible. Adapt a
    // bounded fade margin to dispersion instead of relaxing all quality guards.
    let margin_db = (3.0 + dispersion_db * 0.5).clamp(3.0, 6.0);
    let threshold_dbm = median_dbm - margin_db;
    if require_boundary_range && !(-110.0..=-35.0).contains(&threshold_dbm) {
        return Err(
            "To miejsce jest poza zakresem progu. Wybierz inną granicę odległości od komputera.",
        );
    }
    Ok(CalibrationResult {
        median_dbm,
        threshold_dbm,
        mad_db,
        margin_db,
        sample_count: values.len(),
    })
}
fn median(values: &mut [f64]) -> f64 {
    values.sort_by(f64::total_cmp);
    let middle = values.len() / 2;
    if values.len().is_multiple_of(2) {
        (values[middle - 1] + values[middle]) / 2.0
    } else {
        values[middle]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use brelock_core::signal::estimate_distance;

    #[test]
    fn fits_four_meters_instead_of_the_uncalibrated_one_meter() {
        let current = AppConfig::default();
        let readings: [_; 12] = std::array::from_fn(|i| CalibrationReading {
            t_s: 2.0 + i as f64,
            rssi_dbm: -59.0,
        });
        let result = calibrate_departure_threshold(&readings).unwrap();
        assert_eq!(estimate_distance(result.median_dbm, &current), Some(1.0));
        let fitted = result.calibrated_config(&current, 4.0).unwrap();
        assert!((estimate_distance(-59.0, &fitted).unwrap() - 4.0).abs() < 1e-9);
        assert!((fitted.reference_rssi_dbm - (-45.7546801908)).abs() < 1e-8);
        assert_eq!(fitted.path_loss_exponent, current.path_loss_exponent);
        assert_eq!(fitted.departure_threshold_dbm, Some(result.threshold_dbm));
        assert_eq!(fitted.calibration_distance_m, 4.0);
        assert_eq!(current, AppConfig::default());
    }

    #[test]
    fn fits_known_distances_and_keeps_the_same_scale_after_serialization() {
        let readings: [_; 12] = std::array::from_fn(|i| CalibrationReading {
            t_s: 2.0 + i as f64,
            rssi_dbm: -68.5,
        });
        let result = calibrate_departure_threshold(&readings).unwrap();
        for distance_m in [0.5, 1.0, 4.0, 8.3, 20.0] {
            let fitted = result
                .calibrated_config(&AppConfig::default(), distance_m)
                .unwrap();
            let restored: AppConfig =
                serde_json::from_str(&serde_json::to_string(&fitted).unwrap()).unwrap();
            assert!(
                (estimate_distance(result.median_dbm, &restored).unwrap() - distance_m).abs()
                    < 1e-9
            );
            assert_eq!(restored.departure_threshold_dbm, Some(result.threshold_dbm));
        }
        for invalid in [0.0, -4.0, 0.49, 20.1, f64::NAN, f64::INFINITY] {
            assert!(
                result
                    .calibrated_config(&AppConfig::default(), invalid)
                    .is_err()
            );
        }
    }

    fn feed(run: &mut CalibrationMeasurement, start: f64, end: f64, cadence: f64, noise: f64) {
        let mut t_s = start;
        let mut index = 0;
        while t_s <= end + 0.00001 {
            run.observe(CalibrationReading {
                t_s,
                rssi_dbm: -66.0 + if index % 2 == 0 { noise } else { -noise },
            });
            index += 1;
            t_s += cadence;
        }
    }
    #[test]
    fn measures_after_marker_and_discards_walk_and_touch() {
        let mut run = CalibrationMeasurement::new(10.0);
        for t_s in [5.0, 9.0, 10.0, 11.9] {
            run.observe(CalibrationReading {
                t_s,
                rssi_dbm: -40.0,
            });
        }
        feed(&mut run, 12.0, 22.0, 0.5, 1.0);
        let result = run.poll(22.0).result.unwrap();
        assert_eq!(result.median_dbm, -65.0);
        assert_eq!(result.threshold_dbm, -68.5);
    }
    #[test]
    fn accepts_one_hz_and_normal_radio_noise() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 12.0, 1.0, 5.0);
        let result = run.poll(12.0).result.unwrap();
        assert_eq!(result.sample_count, 11);
        assert!((5.0..=6.0).contains(&result.margin_db));
        assert_eq!(run.poll(12.0).percent, 100);
    }
    #[test]
    fn extends_collection_for_sparse_callbacks_without_requiring_another_tap() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 10.4, 1.4, 1.0);
        assert!(run.poll(12.0).result.is_none());
        run.observe(CalibrationReading {
            t_s: 13.2,
            rssi_dbm: -66.0,
        });
        assert!(run.poll(13.2).result.is_some());
    }
    #[test]
    fn accepts_slow_half_hz_radio_with_a_longer_real_window() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 12.0, 2.0, 1.0);
        assert!(run.poll(12.0).result.is_none());
        feed(&mut run, 14.0, 16.0, 2.0, 1.0);
        assert!(run.poll(16.0).result.is_some());
    }
    #[test]
    fn never_saves_persistent_large_dispersion() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 35.0, 0.5, 12.0);
        let progress = run.poll(35.0);
        assert!(progress.result.is_none());
        assert!(progress.timed_out);
    }
    #[test]
    fn duplicates_invalid_samples_and_bursts_cannot_fill_the_measurement() {
        let mut run = CalibrationMeasurement::new(0.0);
        for i in 0..1000 {
            run.observe(CalibrationReading {
                t_s: 2.0 + i as f64 * 0.0001,
                rssi_dbm: -60.0,
            });
        }
        run.observe(CalibrationReading {
            t_s: f64::NAN,
            rssi_dbm: -60.0,
        });
        run.observe(CalibrationReading {
            t_s: 3.0,
            rssi_dbm: 127.0,
        });
        assert_eq!(run.poll(12.0).sample_count, 1);
        assert!(run.poll(35.0).timed_out);
    }
    #[test]
    fn does_not_save_stale_or_gapped_radio_data() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 10.0, 1.0, 1.0);
        assert!(run.poll(13.0).result.is_none());
        run.observe(CalibrationReading {
            t_s: 14.0,
            rssi_dbm: -66.0,
        });
        assert!(run.poll(14.0).result.is_none());
    }
    #[test]
    fn rejects_drift_but_recovers_with_a_stationary_window() {
        let mut run = CalibrationMeasurement::new(0.0);
        for index in 0..21 {
            run.observe(CalibrationReading {
                t_s: 2.0 + index as f64 * 0.5,
                rssi_dbm: -40.0 - index as f64,
            });
        }
        assert!(run.poll(12.0).result.is_none());
        feed(&mut run, 12.5, 33.0, 0.5, 1.0);
        assert!(run.poll(33.0).result.is_some());
    }
    #[test]
    fn outliers_do_not_pull_the_threshold_and_progress_never_moves_backwards() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 7.0, 0.5, 0.0);
        let percent = run.poll(7.0).percent;
        assert!(run.poll(20.0).percent >= percent);
        feed(&mut run, 20.5, 30.5, 0.5, 0.0);
        run.observe(CalibrationReading {
            t_s: 31.0,
            rssi_dbm: -100.0,
        });
        assert_eq!(run.poll(31.0).result.unwrap().threshold_dbm, -69.0);
    }
    #[test]
    fn strong_signals_are_counted_and_report_range_error_instead_of_missing_samples() {
        let mut run = CalibrationMeasurement::new(0.0);
        for index in 0..11 {
            run.observe(CalibrationReading {
                t_s: 2.0 + index as f64,
                rssi_dbm: -20.0,
            });
        }
        let progress = run.poll(12.0);
        assert_eq!(progress.sample_count, 11);
        assert!(progress.message.contains("zakresem progu"));
        assert!(progress.result.is_none());
    }
    #[test]
    fn cannot_complete_before_required_measurement_time() {
        let mut run = CalibrationMeasurement::new(0.0);
        feed(&mut run, 2.0, 11.5, 0.25, 0.0);
        assert!(run.poll(11.5).result.is_none());
        assert!(run.poll(12.0).result.is_some());
    }
}
