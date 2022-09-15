# Changelog

## v5.2.3

### Fixed
- A111: Unclear-ness in the Calibration management section.
  Users are now able see if calibrations are used by the processor or not.

## v5.2.2

### Removed
- Temporally disable auto-connect functionality because it introduced issues
  related to flashing

## v5.2.1

### Fixed
- Cache-related bug that made Distance Detector unusable.

### v5.2.0
- Platform setup script that is ran with `python -m acconeer.exptool.setup`.
- Sensor selection for Presence- and Distance detector.

## v5.1.0

### Added
- Platform-specific setup scripts
- A121 distance detector: Distance offset calibration
- A121 distance detector: Noise calibration
- A121 presence detector: Settings for profile and step length

### Changed
- A121 distance detector: Account for processing gain when calculating
  HWAAS.

### Fixed
- Fix sensor selection bug on disconnect.
- Only detect USB devices on Windows.

## v5.0.4

### Added
- Support for "simple" A121 records to the `convert_to_csv` utility.
- Sensor id selection to the new A121 application.

## v5.0.3

### Fixed
- Fix version parsing for a111. Version string "a111-vx.x.x" is now
  handled properly.

## v5.0.2

### Fixed
- Fix client timeout when auto-detecting port

## v5.0.1

### Added
- Add *.orig to .gitignore
- Add A121 EVK setup to readme

### Changed
- Bump A111 SDK version to 2.12.0

### Fixed
- Make clean up after stop session more stable
- Set link timeout depending on server update rate and sweep rate

## v5.0.0

This major release provides initial support for the A121, with a new
app, new algorithms, and a stable core API.

No changes has been made to the old application nor the A111 API.

### Added
- A new application, currently only for A121. In the future, A111 will
  be supported in this new app as well, removing the need for two
  separate apps.
- Support for A121 v0.4, amongst other things adding a
  `double_buffering` parameter to `a121.SensorConfig`.
- A121: Initial version of a distance detector.
- A121: Initial version of a presence detector.
- A121: XC120 WinUSB support, for improved data streaming performance
  on Windows.
- A121: Ability to load record from file to RAM.

### Fixed
- A121: Several minor issues in the core API.
- Avoid incompatible dependencies.

## v4.4.1

### Changed
 - Remove references to Ubuntu 18.04
 - Moved Parking to examples

### Fixed
 - Add sampling mode for Sparse in configuration.
   Was accidentally removed, when sampling mode was removed for IQ.
 - Add sampling mode for Sparse when exporting C code.

## v4.4.0

### Added
- `enable_loopback` parameter to `a121.SubsweepConfig`.
- Side/pole mounted case for parking detector.
  Modifies some default settings as well as slight changes in computations.

### Fixed
- Bug that made `a121.Client` not stop its session
  if the session was started with a recorder.

## v4.3.0

### Added
- Unstable (but fully featured) library for the A121 sensor
  generation under `acconeer.exptool.a121`.

## v4.2.0

### Added
- Possibility to export Sensor configuration to C code for use with RSS.

### Changed
 - Update demo images in sensor introduction

### Fixed
- The update rate when replaying a saved file is now
  the same as the file was captured in.

## v4.1.1

### Changed
 - Bump A111 SDK version to v2.11.1

## v4.1.0

### Added
- Wave to exit algorithm added.
- Tank level algorithm for small tanks.

## v4.0.4

### Fixed
- Issue where Exploration tool could not be run on Python 3.7.


## v4.0.3

### Added
- Control for amount of peaks plotted in Distance Detector.

### Fixed
- Implicit behavior of calibration application. Now never applies a
  calibration unless explicitly done by the user.


## v4.0.2

### Changed
- Module server protocol is now default for UART connections in examples

### Fixed
- Outdated referenced to `recording` module in File format reference (docs)
- Bug that did not allow examples and standalones to be run over UART


## v4.0.1

### Changed
- Bump A111 SDK version to 2.11.0


## v4.0.0

### Added
- Command line arguments `--no-config` and `--purge-config` which lets you
  manage files that the Exptool app produces.
- Installation via PyPI with `python -m pip install acconeer-exptool`
- requirements-dev.txt for developers
- Common calibration interface for processors
- Deprecation warning on Streaming Server
- Drop down list in app to select server protocol


### Changed
- Change of nomenclature regarding the GUI, is now called *"the app"*.
- The Exptool app is now part of the `acconeer-exptool` package! Is now run
  with `python -m acconeer.exptool.app` instead of `python gui/main.py`
- Detector- and Service standalone examples have been moved into the
  `acconeer-exptool`-package. (`acconeer.exptool.a111.algo` to be precise.)
- Some algorithm modules have been renamed
- Standalones are now runnable with
  `python -m acconeer.exptool.a111.algo.<service or detector>`
- `internal/` renamed to `tools/`. Still intended for internal use.
- Structure of standalones are separated into
  `processor`- and `ui` modules
- Reduced code duplication of standalones' main functions.
- App sessions are saved to a standard user location instead of the current
  directory.
- Move package dependencies to setup.cfg from requirements.txt (Removing
  requirements.txt and requirements_client_only.txt). Add extras algo and app
  to define additional dependencies.
- Replace tox with nox
- Update python version for portable to 3.9.10
- Update run and update batch files for portable version for Windows. Old
  portable version is no longer compatible.
- SDK version is now specific for A111 (acconeer.exptool.a111.SDK_VERSION)

### Removed
- Machine Learning GUI
- imock
- Sensor fusion in obstacle
- Multi-sensor support in distance and obstacle
- WSL support
- Legacy dict based processing configuration interface
- Legacy calibration interfaces
