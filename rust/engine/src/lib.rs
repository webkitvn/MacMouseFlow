#![forbid(unsafe_code)]

//! Platform-neutral input evaluation.

use std::sync::atomic::{AtomicU32, Ordering};

/// A normalized input observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InputEvent {
    /// A scroll observation.
    Scroll(ScrollEvent),
}

/// A normalized scroll observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ScrollEvent {
    /// The event's explicit source.
    pub source: InputSource,
    /// The semantic unit of the movement.
    pub granularity: ScrollGranularity,
    /// Horizontal line movement.
    pub horizontal_lines: i64,
    /// Vertical line movement.
    pub vertical_lines: i64,
}

/// The visible source of an input observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InputSource {
    /// The source classification supplied by the adapter.
    pub source_class: SourceClass,
}

/// A semantic source classification.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SourceClass {
    /// A mouse source.
    Mouse,
    /// A trackpad source.
    Trackpad,
    /// A source whose class is unavailable.
    Unknown,
}

/// The semantic unit of a scroll observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ScrollGranularity {
    /// Discrete line movement.
    LineBased,
    /// Continuous pixel movement.
    PixelBased,
}

/// User-selected scroll behavior.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ScrollConfiguration {
    direction: ScrollDirection,
    amount_percent: u32,
}

impl ScrollConfiguration {
    /// Preserves the platform's configured direction.
    #[must_use]
    pub const fn system() -> Self {
        Self {
            direction: ScrollDirection::System,
            amount_percent: 100,
        }
    }

    /// Reverses eligible line-based movement.
    #[must_use]
    pub const fn reverse() -> Self {
        Self {
            direction: ScrollDirection::Reverse,
            amount_percent: 100,
        }
    }

    /// Selects an exact integer Scroll Amount, rejecting values outside 25...400.
    #[must_use]
    pub const fn with_amount(self, amount_percent: u32) -> Option<Self> {
        if amount_percent < 25 || amount_percent > 400 {
            return None;
        }
        Some(Self {
            amount_percent,
            ..self
        })
    }

    const fn snapshot(self) -> u32 {
        (self.amount_percent << 1) | self.direction as u32
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ScrollDirection {
    System,
    Reverse,
}

/// The result to apply to an input observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InputDecision {
    /// Leave the native observation unchanged.
    Preserve,
    /// Replace line-based movement with exact hundredths-of-a-line.
    Replace(LineBasedReplacement),
}

/// Exact replacement movement; 100 hundredths equals one line.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LineBasedReplacement {
    /// Horizontal movement in hundredths-of-a-line.
    pub horizontal_hundredths: i64,
    /// Vertical movement in hundredths-of-a-line.
    pub vertical_hundredths: i64,
}

/// An evaluation status independent of the decision.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EvaluationStatus {
    /// Evaluation completed normally.
    Success,
    /// Evaluation could not safely produce a replacement.
    EvaluationFailed,
}

/// An evaluation status and input decision.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Evaluation {
    /// The evaluation result code.
    pub status: EvaluationStatus,
    /// The decision that native code can safely apply.
    pub decision: InputDecision,
}

impl Evaluation {
    /// Creates a successful evaluation.
    #[must_use]
    pub const fn success(decision: InputDecision) -> Self {
        Self {
            status: EvaluationStatus::Success,
            decision,
        }
    }

    const fn failed() -> Self {
        Self {
            status: EvaluationStatus::EvaluationFailed,
            decision: InputDecision::Preserve,
        }
    }
}

/// Evaluates platform-neutral input against an atomic configuration snapshot.
pub struct Engine {
    configuration: AtomicU32,
}

impl Engine {
    /// Creates an engine with the supplied configuration.
    #[must_use]
    pub fn new(configuration: ScrollConfiguration) -> Self {
        Self {
            configuration: AtomicU32::new(configuration.snapshot()),
        }
    }

    /// Replaces the configuration observed by later evaluations.
    pub fn set_configuration(&self, configuration: ScrollConfiguration) {
        self.configuration
            .store(configuration.snapshot(), Ordering::Release);
    }

    /// Evaluates one normalized input observation.
    #[must_use]
    pub fn evaluate(&self, event: InputEvent) -> Evaluation {
        match event {
            InputEvent::Scroll(scroll) => self.evaluate_scroll(scroll),
        }
    }

    fn evaluate_scroll(&self, scroll: ScrollEvent) -> Evaluation {
        let snapshot = self.configuration.load(Ordering::Acquire);
        let amount = i64::from(snapshot >> 1);
        let reverse = snapshot & 1 == ScrollDirection::Reverse as u32;
        if scroll.granularity == ScrollGranularity::PixelBased
            || (!reverse && amount == 100)
            || (scroll.horizontal_lines == 0 && scroll.vertical_lines == 0)
        {
            return Evaluation::success(InputDecision::Preserve);
        }

        let scale = |lines: i64| {
            let hundredths = lines.checked_mul(amount)?;
            if reverse {
                hundredths.checked_neg()
            } else {
                Some(hundredths)
            }
        };
        let Some(horizontal_hundredths) = scale(scroll.horizontal_lines) else {
            return Evaluation::failed();
        };
        let Some(vertical_hundredths) = scale(scroll.vertical_lines) else {
            return Evaluation::failed();
        };

        Evaluation::success(InputDecision::Replace(LineBasedReplacement {
            horizontal_hundredths,
            vertical_hundredths,
        }))
    }
}
