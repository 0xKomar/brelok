//! A confirmed, stationary RSSI measurement at each of 1, 2 and 3 metres.
//! Partial points never change the live configuration. Time alone cannot
//! confirm that the user has reached the next physical position.
use crate::calibration::{CalibrationMeasurement, CalibrationReading, CalibrationResult};
use brelock_core::{AppConfig, config::ConfigError};
use serde::Serialize;

pub const CALIBRATION_DISTANCES_M: [f64; 3] = [1.0, 2.0, 3.0];
pub const MOVE_SECONDS: f64 = 2.0;
const MIN_DROP_DB: f64 = 3.0;
const MAX_REVERSAL_DB: f64 = 2.0;
const MAX_FIT_RMSE_DB: f64 = 3.0;
const MIN_FIT_R_SQUARED: f64 = 0.75;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GuidedPhase {
    Idle,
    MovingToPoint,
    WaitingForMarker,
    Collecting,
    Complete,
}
impl GuidedPhase {
    pub fn is_active(self) -> bool {
        matches!(
            self,
            Self::MovingToPoint | Self::WaitingForMarker | Self::Collecting
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct CalibrationPoint {
    pub distance_m: f64,
    #[serde(flatten)]
    pub result: CalibrationResult,
}

#[derive(Debug, Clone, PartialEq)]
pub struct MultipointResult {
    pub reference_rssi_dbm: f64,
    pub path_loss_exponent: f64,
    pub rmse_db: f64,
    pub r_squared: f64,
    pub points: Vec<CalibrationPoint>,
}
impl MultipointResult {
    pub fn calibrated_config(&self, current: &AppConfig) -> Result<AppConfig, ConfigError> {
        let boundary = self
            .points
            .last()
            .ok_or(ConfigError("missing calibration boundary"))?;
        let config = AppConfig {
            reference_rssi_dbm: self.reference_rssi_dbm,
            path_loss_exponent: self.path_loss_exponent,
            calibration_distance_m: boundary.distance_m,
            departure_threshold_dbm: Some(boundary.result.threshold_dbm),
            ..current.clone()
        };
        config.validate()?;
        Ok(config)
    }
}

/// Equal weight per stationary point: high callback rates do not dominate the fit.
/// RSSI = A - 10*n*log10(distance). Reject a poor fit instead of clamping n.
pub fn fit_points(points: &[CalibrationPoint]) -> Result<MultipointResult, &'static str> {
    if points.len() != CALIBRATION_DISTANCES_M.len()
        || points
            .iter()
            .zip(CALIBRATION_DISTANCES_M)
            .any(|(point, distance)| {
                point.distance_m != distance
                    || !point.result.median_dbm.is_finite()
                    || !point.result.threshold_dbm.is_finite()
                    || !(-127.0..=-1.0).contains(&point.result.median_dbm)
            })
    {
        return Err("Potrzebne są trzy poprawne pomiary: 1, 2 i 3 m.");
    }
    if points[0].result.median_dbm - points[2].result.median_dbm < MIN_DROP_DB
        || points
            .windows(2)
            .any(|p| p[1].result.median_dbm - p[0].result.median_dbm > MAX_REVERSAL_DB)
    {
        return Err(
            "Sygnał nie słabnie wystarczająco wraz z odległością. Sprawdź punkty i zachowaj tę samą pozycję breloka.",
        );
    }
    let x_mean = points.iter().map(|p| p.distance_m.log10()).sum::<f64>() / 3.0;
    let y_mean = points.iter().map(|p| p.result.median_dbm).sum::<f64>() / 3.0;
    let sxx = points
        .iter()
        .map(|p| (p.distance_m.log10() - x_mean).powi(2))
        .sum::<f64>();
    let slope = points
        .iter()
        .map(|p| (p.distance_m.log10() - x_mean) * (p.result.median_dbm - y_mean))
        .sum::<f64>()
        / sxx;
    let n = -slope / 10.0;
    let a = y_mean - slope * x_mean;
    if !n.is_finite() || !(0.5..=6.0).contains(&n) || !a.is_finite() {
        return Err(
            "Wyliczony współczynnik n jest poza zakresem 0,5–6. Powtórz serię w tej samej pozycji noszenia.",
        );
    }
    let residual = points
        .iter()
        .map(|p| (p.result.median_dbm - (a + slope * p.distance_m.log10())).powi(2))
        .sum::<f64>();
    let syy = points
        .iter()
        .map(|p| (p.result.median_dbm - y_mean).powi(2))
        .sum::<f64>();
    let rmse_db = (residual / 3.0).sqrt();
    let r_squared = (1.0 - residual / syy).clamp(0.0, 1.0);
    if rmse_db > MAX_FIT_RMSE_DB || r_squared < MIN_FIT_R_SQUARED {
        return Err(
            "Pomiary nie pasują do jednego modelu odległości. Powtórz serię bez zmiany orientacji breloka.",
        );
    }
    Ok(MultipointResult {
        reference_rssi_dbm: a,
        path_loss_exponent: n,
        rmse_db,
        r_squared,
        points: points.to_vec(),
    })
}

#[derive(Debug)]
pub struct GuidedProgress {
    pub phase: GuidedPhase,
    pub step: u8,
    pub distance_m: f64,
    pub movement_remaining_s: f64,
    pub sample_count: usize,
    pub point_percent: u8,
    pub percent: u8,
    pub elapsed_s: f64,
    pub message: String,
    pub points: Vec<CalibrationPoint>,
    pub result: Option<MultipointResult>,
    pub notice: Option<String>,
}

#[derive(Debug)]
pub struct GuidedCalibration {
    phase: GuidedPhase,
    points: Vec<CalibrationPoint>,
    move_until_s: f64,
    measurement: Option<CalibrationMeasurement>,
    result: Option<MultipointResult>,
    message: String,
    notice: Option<String>,
    restart_note: Option<String>,
}
impl GuidedCalibration {
    pub fn new(at_s: f64) -> Self {
        Self {
            phase: GuidedPhase::MovingToPoint,
            points: vec![],
            move_until_s: at_s + MOVE_SECONDS,
            measurement: None,
            result: None,
            message: "Odejdź na 1 m od laptopa ustawionego na stole.".into(),
            notice: None,
            restart_note: None,
        }
    }
    fn point_index(&self) -> usize {
        self.points.len().min(2)
    }
    pub fn begin_measurement(&mut self, at_s: f64) -> Result<(), &'static str> {
        if self.phase != GuidedPhase::WaitingForMarker {
            return Err(
                "Poczekaj na odliczanie, ustaw się w oznaczonym punkcie i potwierdź POMIAR.",
            );
        }
        self.measurement = Some(if self.point_index() < 2 {
            CalibrationMeasurement::model_point(at_s)
        } else {
            CalibrationMeasurement::new(at_s)
        });
        self.phase = GuidedPhase::Collecting;
        Ok(())
    }
    pub fn observe(&mut self, reading: CalibrationReading) {
        if let Some(measurement) = self.measurement.as_mut() {
            measurement.observe(reading);
        }
    }
    pub fn retry_point(&mut self, message: String) {
        self.measurement = None;
        self.phase = GuidedPhase::WaitingForMarker;
        self.message = message;
    }
    /// Reboot, invalid fit or failed save must not mix runs or retain a completed fit.
    pub fn restart(&mut self, at_s: f64, message: String) {
        *self = Self::new(at_s);
        self.message = message.clone();
        self.restart_note = Some(message);
    }
    pub fn poll(&mut self, at_s: f64) -> GuidedProgress {
        if self.phase == GuidedPhase::MovingToPoint && at_s >= self.move_until_s {
            self.phase = GuidedPhase::WaitingForMarker;
            let instruction = format!(
                "Jesteś na {} m? Przytrzymaj POMIAR przez 3 s, potem pozostań w miejscu.",
                CALIBRATION_DISTANCES_M[self.point_index()]
            );
            self.message = match self.restart_note.take() {
                Some(note) => format!("{note} {instruction}"),
                None => instruction,
            };
        }
        let mut sample_count = 0;
        let mut point_percent = 0;
        let mut elapsed_s = 0.0;
        if let Some(measurement) = self.measurement.as_mut() {
            let progress = measurement.poll(at_s);
            sample_count = progress.sample_count;
            point_percent = progress.percent;
            elapsed_s = progress.elapsed_s;
            self.message = progress.message.into();
            if let Some(result) = progress.result {
                self.points.push(CalibrationPoint {
                    distance_m: CALIBRATION_DISTANCES_M[self.point_index()],
                    result,
                });
                self.measurement = None;
                if self.points.len() == CALIBRATION_DISTANCES_M.len() {
                    match fit_points(&self.points) {
                        Ok(fit) => {
                            self.result = Some(fit);
                            self.phase = GuidedPhase::Complete;
                        }
                        Err(error) => {
                            let message = format!(
                                "{error} Poprzednie ustawienia zachowano. Zacznij ponownie od 1 m."
                            );
                            self.restart(at_s, message.clone());
                            self.notice = Some(message);
                        }
                    }
                } else {
                    self.phase = GuidedPhase::MovingToPoint;
                    self.move_until_s = at_s + MOVE_SECONDS;
                    self.message = format!(
                        "Punkt zapisany w serii. Cofnij się o 1 m — na {} m od laptopa.",
                        CALIBRATION_DISTANCES_M[self.point_index()]
                    );
                }
                sample_count = 0;
                point_percent = 0;
                elapsed_s = 0.0;
            } else if progress.timed_out {
                let message = format!(
                    "Pomiar {} m nie zakończył się w 35 s. {} Potwierdź POMIAR ponownie w tym samym punkcie; poprzednie ustawienia zachowano.",
                    CALIBRATION_DISTANCES_M[self.point_index()],
                    progress.message
                );
                self.retry_point(message.clone());
                self.notice = Some(message);
                point_percent = 0;
            }
        }
        let percent = if self.phase == GuidedPhase::Complete {
            100
        } else {
            ((self.points.len() * 100 + usize::from(point_percent)) / 3) as u8
        };
        GuidedProgress {
            phase: self.phase,
            step: self.point_index() as u8 + 1,
            distance_m: CALIBRATION_DISTANCES_M[self.point_index()],
            movement_remaining_s: if self.phase == GuidedPhase::MovingToPoint {
                (self.move_until_s - at_s).max(0.0)
            } else {
                0.0
            },
            sample_count,
            point_percent,
            percent,
            elapsed_s,
            message: self.message.clone(),
            points: self.points.clone(),
            result: self.result.clone(),
            notice: self.notice.take(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use brelock_core::signal::estimate_distance;
    fn point(distance_m: f64, median_dbm: f64) -> CalibrationPoint {
        CalibrationPoint {
            distance_m,
            result: CalibrationResult {
                median_dbm,
                threshold_dbm: median_dbm - 4.0,
                mad_db: 2.0,
                margin_db: 4.0,
                sample_count: 12,
            },
        }
    }
    fn ideal(a: f64, n: f64) -> Vec<CalibrationPoint> {
        CALIBRATION_DISTANCES_M
            .iter()
            .map(|d| point(*d, a - 10.0 * n * d.log10()))
            .collect()
    }
    #[test]
    fn three_points_recover_both_model_parameters_and_the_boundary() {
        for n in [0.8, 2.2, 3.5, 5.5] {
            let fit = fit_points(&ideal(-45.0, n)).unwrap();
            assert!((fit.reference_rssi_dbm + 45.0).abs() < 1e-9);
            assert!((fit.path_loss_exponent - n).abs() < 1e-9);
            let original = AppConfig::default();
            let config = fit.calibrated_config(&original).unwrap();
            for point in &fit.points {
                assert!(
                    (estimate_distance(point.result.median_dbm, &config).unwrap()
                        - point.distance_m)
                        .abs()
                        < 1e-9
                );
            }
            assert_eq!(
                config.departure_threshold_dbm,
                Some(fit.points[2].result.threshold_dbm)
            );
            assert_eq!(config.calibration_distance_m, 3.0);
            assert_eq!(original, AppConfig::default());
        }
    }
    #[test]
    fn invalid_series_is_rejected_instead_of_clamping_or_saving() {
        for values in [
            [-50.0, -50.0, -50.0],
            [-70.0, -60.0, -50.0],
            [-45.0, -70.0, -49.0],
            [-30.0, -55.0, -70.0],
        ] {
            let points: Vec<_> = CALIBRATION_DISTANCES_M
                .into_iter()
                .zip(values)
                .map(|(d, r)| point(d, r))
                .collect();
            assert!(fit_points(&points).is_err());
        }
        let mut points = ideal(-45.0, 2.2);
        points[1].result.median_dbm = f64::NAN;
        assert!(fit_points(&points).is_err());
        assert!(fit_points(&points[..2]).is_err());
        points = ideal(-45.0, 2.2);
        points[1].distance_m = 1.0;
        assert!(fit_points(&points).is_err());
    }
    #[test]
    fn small_stationary_noise_fits_without_callback_rate_weighting() {
        let mut points = ideal(-45.0, 2.2);
        points[1].result.median_dbm += 0.75;
        points[1].result.sample_count = 100;
        let fit = fit_points(&points).unwrap();
        points[1].result.sample_count = 8;
        let other = fit_points(&points).unwrap();
        assert_eq!(fit.reference_rssi_dbm, other.reference_rssi_dbm);
        assert_eq!(fit.path_loss_exponent, other.path_loss_exponent);
        assert!(fit.rmse_db < 0.5 && fit.r_squared > 0.99);
    }
    fn collect(run: &mut GuidedCalibration, at_s: f64, rssi: f64) -> GuidedProgress {
        run.begin_measurement(at_s).unwrap();
        assert!(run.begin_measurement(at_s + 1.0).is_err());
        for i in 0..13 {
            run.observe(CalibrationReading {
                t_s: at_s + i as f64,
                rssi_dbm: rssi,
            });
        }
        run.poll(at_s + 12.0)
    }
    #[test]
    fn each_position_requires_confirmation_and_moving_samples_are_excluded() {
        let mut run = GuidedCalibration::new(0.0);
        assert!(run.begin_measurement(1.0).is_err());
        let mut progress = run.poll(2.0);
        assert_eq!(progress.phase, GuidedPhase::WaitingForMarker);
        assert!(progress.result.is_none());
        let expected = ideal(-45.0, 2.2);
        for (index, point) in expected.iter().enumerate() {
            let at_s = 2.0 + index as f64 * 14.0;
            run.observe(CalibrationReading {
                t_s: at_s - 0.2,
                rssi_dbm: -100.0,
            });
            assert_eq!(progress.distance_m, point.distance_m);
            progress = collect(&mut run, at_s, point.result.median_dbm);
            if index < 2 {
                assert_eq!(progress.phase, GuidedPhase::MovingToPoint);
                assert!(progress.result.is_none());
                assert_eq!(progress.movement_remaining_s, 2.0);
                assert!(run.begin_measurement(at_s + 13.0).is_err());
                progress = run.poll(at_s + 14.0);
                assert_eq!(progress.phase, GuidedPhase::WaitingForMarker);
            }
        }
        assert_eq!(progress.phase, GuidedPhase::Complete);
        assert_eq!(progress.percent, 100);
        let fit = progress.result.unwrap();
        assert!((fit.path_loss_exponent - 2.2).abs() < 1e-9);
        assert!(fit.points.iter().all(|p| p.result.sample_count == 11));
    }
    #[test]
    fn strong_near_signal_is_valid_for_the_model_but_only_three_meters_sets_the_boundary() {
        let mut run = GuidedCalibration::new(0.0);
        let expected = ideal(-30.0, 2.2);
        for (index, point) in expected.iter().enumerate() {
            let at_s = 2.0 + index as f64 * 14.0;
            run.poll(at_s);
            collect(&mut run, at_s, point.result.median_dbm);
        }
        let fit = run.poll(42.0).result.unwrap();
        assert!(fit.points[0].result.threshold_dbm > -35.0);
        let config = fit.calibrated_config(&AppConfig::default()).unwrap();
        assert!(config.departure_threshold_dbm.unwrap() < -35.0);
        assert!((config.reference_rssi_dbm + 30.0).abs() < 1e-9);
    }
    #[test]
    fn timeout_retries_only_current_point_and_restart_discards_partial_points() {
        let mut run = GuidedCalibration::new(0.0);
        run.poll(2.0);
        collect(&mut run, 2.0, -45.0);
        run.poll(16.0);
        run.begin_measurement(16.0).unwrap();
        let progress = run.poll(51.0);
        assert_eq!(progress.phase, GuidedPhase::WaitingForMarker);
        assert_eq!(progress.step, 2);
        assert_eq!(progress.points.len(), 1);
        assert!(progress.notice.is_some());
        assert!(run.poll(52.0).notice.is_none());
        run.restart(
            53.0,
            "Restart breloka; poprzednie ustawienia zachowano.".into(),
        );
        let progress = run.poll(55.0);
        assert_eq!(progress.step, 1);
        assert!(progress.points.is_empty());
        assert!(progress.result.is_none());
    }
    #[test]
    fn rejected_final_fit_restarts_series_without_a_config_result() {
        let mut run = GuidedCalibration::new(0.0);
        for index in 0..3 {
            let at_s = 2.0 + index as f64 * 14.0;
            run.poll(at_s);
            collect(&mut run, at_s, -50.0);
        }
        let progress = run.poll(42.0);
        assert_eq!(progress.phase, GuidedPhase::MovingToPoint);
        assert_eq!(progress.step, 1);
        assert!(progress.result.is_none());
        assert!(progress.points.is_empty());
        let ready = run.poll(44.0);
        assert_eq!(ready.phase, GuidedPhase::WaitingForMarker);
        assert!(ready.message.contains("Poprzednie ustawienia zachowano"));
    }
}
