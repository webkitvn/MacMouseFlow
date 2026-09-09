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
}

impl ScrollConfiguration {
    /// Preserves the platform's configured direction.
    #[must_use]
    pub const fn system() -> Self {
        Self {
            direction: ScrollDirection::System,
        }
    }

    /// Reverses eligible line-based movement.
    #[must_use]
    pub const fn reverse() -> Self {
        Self {
            direction: ScrollDirection::Reverse,
        }
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
    /// Replace it with the normalized scroll observation.
    Replace(ScrollEvent),
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
    direction: AtomicU32,
}

impl Engine {
    /// Creates an engine with the supplied configuration.
    #[must_use]
    pub fn new(configuration: ScrollConfiguration) -> Self {
        Self {
            direction: AtomicU32::new(configuration.direction as u32),
        }
    }

    /// Replaces the configuration observed by later evaluations.
    pub fn set_configuration(&self, configuration: ScrollConfiguration) {
        self.direction
            .store(configuration.direction as u32, Ordering::Release);
    }

    /// Evaluates one normalized input observation.
    #[must_use]
    pub fn evaluate(&self, event: InputEvent) -> Evaluation {
        match event {
            InputEvent::Scroll(scroll) => self.evaluate_scroll(scroll),
        }
    }

    fn evaluate_scroll(&self, scroll: ScrollEvent) -> Evaluation {
        if scroll.granularity == ScrollGranularity::PixelBased
            || self.direction.load(Ordering::Acquire) == ScrollDirection::System as u32
            || (scroll.horizontal_lines == 0 && scroll.vertical_lines == 0)
        {
            return Evaluation::success(InputDecision::Preserve);
        }

        let Some(horizontal_lines) = scroll.horizontal_lines.checked_neg() else {
            return Evaluation::failed();
        };
        let Some(vertical_lines) = scroll.vertical_lines.checked_neg() else {
            return Evaluation::failed();
        };

        Evaluation::success(InputDecision::Replace(ScrollEvent {
            horizontal_lines,
            vertical_lines,
            ..scroll
        }))
    }
}
