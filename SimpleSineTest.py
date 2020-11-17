# flake8: noqa: E402
import itertools
import os

from catkit.catkit_types import quantity, units, SinSpecification, FpmPosition, LyotStopPosition, \
    ImageCentering  # noqa: E402
from catkit.hardware.boston.sin_command import sin_command  # noqa: E402
from catkit.hardware.boston.commands import flat_command
from hicat.config import CONFIG_INI  # noqa: E402
from hicat.experiments.Experiment import Experiment  # noqa: E402
from hicat.experiments.modules import iris_ao
from hicat.hardware import testbed  # noqa: E402
import hicat.util  # noqa: E402


class SimpleSineTest(Experiment):
    """
    Apply the same sine waves to both DMs, with a defined phase shift and get a focal plane image.

    This reads the DM translation from the simulator section in the configfile and applies it if this is run on the
    simulator. If run on hwardware, the DM translation from the config.ini will still be used to create teh full data
    path.
    :param cycles: range, cycles per aperture (spatial frequency) in lambda/D
    :param orientation_angles: list, rotation angles for the sine wave in degrees
    :param phase_shifts: list, phase between DM patterns in degrees - affects relative brightness of resulting speckles
    """
    def __init__(self, cycles, orientation_angles, phase_shifts, exposure_time=None, num_exposures=20):
        super().__init__()
        self.name = 'Sine wave DM alignment tests'
        self.cycles = cycles
        self.orientation_angles = orientation_angles
        self.phase_shifts = phase_shifts
        self.exposure_time = exposure_time
        self.auto_expose = exposure_time is None
        self.num_exposures = num_exposures

    def experiment(self):
        # Get combinations of parameters
        params = itertools.product(self.cycles, self.orientation_angles, self.phase_shifts)

        # Get DM translation settings from config file
        dm_translation_x_microns = int(1e6 * CONFIG_INI.getfloat('boston_kilo952', 'dm2_translation_x'))
        dm_translation_y_microns = int(1e6 * CONFIG_INI.getfloat('boston_kilo952', 'dm2_translation_y'))

        # if we are running in simulation mode, create subdirectory with DM misalignment information
        subdirectory = f'x={dm_translation_x_microns}_y={dm_translation_y_microns}'

        with testbed.dm_controller() as dm, \
                testbed.iris_ao() as iris_dm:
            # First take an image with DMs flat as the baseline, for background subtraction of the rest of the PSF
            # to measure the spots better
            suffix_in = "both_dms_flat"
            dm.apply_shape_to_both(flat_command(bias=False, flat_map=True), flat_command(bias=False, flat_map=True))
            iris_dm.apply_shape(iris_ao.flat_command())

            saveto_path = hicat.util.create_data_path(initial_path=os.path.join(self.output_path, subdirectory),
                                                      suffix=suffix_in)
            testbed.run_hicat_imaging(exposure_time=self.exposure_time,
                                      num_exposures=self.num_exposures,
                                      fpm_position=FpmPosition.coron,
                                      lyot_stop_position=LyotStopPosition.in_beam,
                                      file_mode=True,
                                      raw_skip=self.num_exposures+1,
                                      path=saveto_path,
                                      exposure_set_name='coron',
                                      filename='dms_flat',
                                      auto_expose=self.auto_expose,
                                      centering=ImageCentering.custom_apodizer_spots,
                                      auto_exposure_mask_size=5.5,
                                      resume=False,
                                      pipeline=True)


            # Loop over everything
            for ncyc, angle, phase_shift in params:
                # Create sine waves with
                # SinSpecification = namedtuple("SinSpecification", "angle, ncycles, peak_to_valley, phase")
                ampl = 50  # amplitude in nm
                phase1 = 90
                phase2 = phase1 + phase_shift

                sin_specification_first = SinSpecification(angle, ncyc, quantity(ampl, units.nanometer), phase1)
                sin_specification_second = SinSpecification(angle, ncyc, quantity(ampl, units.nanometer), phase2)

                # Pick an output path
                suffix_in = 'ripple_test_cycl_{}_ang_{}_phase1_{}_phase2_{}'.format(ncyc, angle, phase1, phase2)

                saveto_path = hicat.util.create_data_path(initial_path=os.path.join(self.output_path, subdirectory),
                                                          suffix=suffix_in)

                # Create the actual DM commands
                sin_command_object_dm1, sin_file_name_dm1 = sin_command(sin_specification_first, dm_num=1,
                                                                        return_shortname=True,
                                                                        flat_map=True)
                sin_command_object_dm2, sin_file_name_dm2 = sin_command(sin_specification_second, dm_num=2,
                                                                        return_shortname=True,
                                                                        flat_map=True)

                # Apply the sines to the DMs
                dm.apply_shape(sin_command_object_dm1, dm_num=1)
                dm.apply_shape(sin_command_object_dm2, dm_num=2)

                # Take images
                testbed.run_hicat_imaging(exposure_time=self.exposure_time,
                                          num_exposures=self.num_exposures,
                                          fpm_position=FpmPosition.coron,
                                          lyot_stop_position=LyotStopPosition.in_beam,
                                          file_mode=True,
                                          raw_skip=self.num_exposures + 1,
                                          path=saveto_path,
                                          exposure_set_name='coron',
                                          filename=sin_file_name_dm1,
                                          auto_expose=self.auto_expose,
                                          centering=ImageCentering.custom_apodizer_spots,
                                          auto_exposure_mask_size=5.5,
                                          resume=False,
                                          pipeline=True)
            # Eventually we should extract and record some of the photometry from here, as opposed to measuring that
            # only later in the plot script. For now, just record the existence of this dataset into the calibration DB
            # to make it easier to later script the analysis thereof.
            hicat.calibration_util.record_calibration_measurement(f"Sine wave DM alignment data",
                                                                  -1,
                                                                  'TBD')
