# Pointer Input

Canonical domain language for interpreting pointing-device input and user-configured behavior. Platform API names, transport details, process topology, and implementation state do not belong in this glossary.

## Input

**Pointing Device**:
A physical device that can produce pointer, button, or scroll input.
_Avoid_: Peripheral, HID device

**Input Source**:
The domain-visible origin of an Input Event. It may identify a specific Pointing Device, only classify the source, or remain Unknown when the platform cannot establish more.
_Avoid_: Sender, producer

**Source Class**:
The semantic class of an Input Source used for behavior selection, such as Mouse, Trackpad, or Unknown.
_Avoid_: Device type, hardware type

**Device Identity**:
A stable identity for a Pointing Device when the platform can establish one reliably. Absence of Device Identity must not be treated as proof that two events came from the same device.
_Avoid_: Device ID when referring to a platform-specific identifier

**Device Capability**:
An input behavior or control a Pointing Device is known to provide, such as scrolling or extra buttons.
_Avoid_: Feature, hardware feature

**Input Event**:
A platform-neutral observation of user input after platform-specific data has been normalized into domain meaning.
_Avoid_: Raw input, native event

**Scroll Event**:
An Input Event representing scroll movement along one or more axes.
_Avoid_: Wheel event

**Scroll Granularity**:
The semantic unit of a Scroll Event: LineBased when movement is expressed as discrete line steps, or PixelBased when movement is continuous at pixel precision. Scroll Granularity is an event characteristic and must not be treated as proof of Source Class or Device Identity.
_Avoid_: Mouse scroll, trackpad scroll when only granularity is known

## Configuration

**Scroll Configuration**:
The user-chosen scroll behavior, such as direction or Scroll Amount, applied to a matching Input Source, Source Class, or default scope.
_Avoid_: Scroll settings when referring to the domain concept

**Scroll Amount**:
The user-chosen relative magnitude of LineBased scroll movement. A neutral amount preserves the original magnitude; lower or higher amounts reduce or increase it without defining temporal acceleration, smoothing, or momentum.
_Avoid_: Scroll speed, sensitivity, multiplier when referring to the domain concept

**Device Profile**:
A persistent set of user configuration associated with one Pointing Device.
_Avoid_: Preset, device settings

## Interpretation

**Input Decision**:
The result of evaluating an Input Event: preserve the original input, replace it with transformed input, or suppress it.
_Avoid_: Action when referring to input transformation

**Binding**:
A user-configured relationship from a recognizable input pattern to an Action.
_Avoid_: Mapping, shortcut

**Action**:
A user-visible outcome requested when a Binding matches.
_Avoid_: Command, callback
