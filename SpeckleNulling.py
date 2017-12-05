from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

# noinspection PyUnresolvedReferences
from builtins import *
import os
import numpy as np

from .Experiment import Experiment
from ..hardware.boston.sin_command import sin_command
from ..hardware.boston.commands import flat_command

from ..speckle_nulling import speckle_nulling
from ..hicat_types import units, quantity, FpmPosition, SinSpecification, LyotStopPosition, ImageCentering
from ..hardware import testbed
from ..hardware.boston import DmCommand
from ..config import CONFIG_INI
from .. import util


class SpeckleNulling(Experiment):
    name = "Speckle Nulling"

    def __init__(self,
                 num_iterations=10,
                 bias=False,
                 flat_map=True,
                 path=None,
                 exposure_time=quantity(100, units.millisecond),
                 num_exposures=3,
                 dm_command_path=None,
                 initial_speckles=SinSpecification(10, 12, quantity(25, units.nanometer), 90),
                 suffix=None,
                 fpm_position=FpmPosition.coron,
                 lyot_stop_position=LyotStopPosition.in_beam,
                 centering=ImageCentering.auto,
                 **kwargs):
        self.num_iterations = num_iterations
        self.bias = bias
        self.flat_map = flat_map
        self.path = path
        self.exposure_time = exposure_time
        self.num_exposures = num_exposures
        self.dm_command_path = dm_command_path
        self.initial_speckles = initial_speckles
        self.suffix = suffix
        self.fpm_position = fpm_position
        self.lyot_stop_position = lyot_stop_position
        self.centering = centering
        self.kwargs = kwargs

    def experiment(self):

        # Wait to set the path until the experiment starts (rather than the constructor)
        if self.path is None:
            suffix = "speckle_nulling"
            if self.suffix is not None:
                suffix = suffix + "_" + self.suffix
            self.path = util.create_data_path(suffix=suffix)

        # Start with a previously stored DM command if dm_command_path is passed in.
        if self.dm_command_path:
            current_command_object = DmCommand.load_dm_command(self.dm_command_path,
                                                               bias=self.bias,
                                                               flat_map=self.flat_map)
            file_name = "flat_map" if self.flat_map else "bias"
            if self.initial_speckles:
                print("Ignoring initial speckles and loading dm_command from disk.")

        # Inject sin waves if initial_speckles is passed in.
        elif self.initial_speckles:
            current_command_object, file_name = sin_command(self.initial_speckles, bias=self.bias,
                                                            flat_map=self.flat_map,
                                                            return_shortname=True)

        # Create a flat map or bias command if no dm_command_path or initial_speckles are passed in.
        else:
            current_command_object, file_name = flat_command(bias=self.bias,
                                                             flat_map=self.flat_map,
                                                             return_shortname=True)

        # Set the starting exposure time.
        auto_exposure_time = self.exposure_time

        # Set the exposure set name and laser current based on FPM position.
        if self.fpm_position.value == FpmPosition.coron.value:
            exp_set_name = "coron"
            laser_current = CONFIG_INI.getint("thorlabs_source_mcls1", "coron_current")
        else:
            exp_set_name = "direct"
            laser_current = CONFIG_INI.getint("thorlabs_source_mcls1", "direct_current")

        # Initialize the laser and connect to the DM, apply the sine wave shape.
        with testbed.laser_source() as laser:
            laser.set_current(laser_current)

            with testbed.dm_controller() as dm:

                for i in range(0, self.num_iterations):
                    dm.apply_shape(current_command_object, 1)

                    # Tests the dark zone intensity and updates exposure time if needed, or just returns itself.
                    auto_exposure_time = speckle_nulling.test_dark_zone_intensity(
                        auto_exposure_time, 2,
                        fpm_position=self.fpm_position,
                        lyot_stop_position=self.lyot_stop_position,
                        centering=self.centering)

                    # Take coronographic data, with backgrounds.
                    iteration_path = os.path.join(self.path, "iteration" + str(i))
                    testbed.run_hicat_imaging(auto_exposure_time, self.num_exposures, self.fpm_position,
                                              lyot_stop_position=self.lyot_stop_position,
                                              centering=self.centering,
                                              path=iteration_path, auto_exposure_time=False,
                                              exposure_set_name=exp_set_name, filename="itr" + str(i) + "_" + file_name,
                                              **self.kwargs)

                    # Run sensing.
                    coron_path = os.path.join(iteration_path, exp_set_name)
                    ncycles_new, angle_deg_new, peak_to_valley_new = speckle_nulling.speckle_sensing(coron_path)

                    # Generate a list of sin_commands at different phases, and take data for each.
                    phase_list = range(0, 360, 30)
                    for phi in phase_list:
                        # Add the current dm command into a new sin_command.
                        new_command, name = sin_command(
                            SinSpecification(angle_deg_new, ncycles_new, peak_to_valley_new, phi),
                            bias=self.bias, flat_map=self.flat_map, return_shortname=True,
                            initial_data=current_command_object.data)
                        dm.apply_shape(new_command, 1)

                        phase_path = os.path.join(iteration_path, "phase" + str(phi))

                        testbed.run_hicat_imaging(auto_exposure_time, self.num_exposures, self.fpm_position,
                                                  lyot_stop_position=self.lyot_stop_position,
                                                  path=phase_path, auto_exposure_time=False,
                                                  centering=self.centering,
                                                  exposure_set_name=exp_set_name, filename="itr" + str(i) + "_" + name,
                                                  simulator=False, **self.kwargs)

                    # Run control on the set of phase shifted data.
                    new_phase = speckle_nulling.speckle_control_phase(iteration_path, exp_set_name)

                    # Generate a list of sin_commands a range of amplitudes for the best phase, and take data for each.
                    amplitude_coeff_list = np.arange(0.1, 2.0, 0.3)
                    for ampl_ptv in amplitude_coeff_list:
                        # Add the current dm command into a new sin_command.
                        peak_to_valley_test = peak_to_valley_new * ampl_ptv

                        new_command, name = sin_command(
                            SinSpecification(angle_deg_new, ncycles_new, peak_to_valley_test,
                                             new_phase),
                            bias=self.bias, flat_map=self.flat_map, return_shortname=True,
                            initial_data=current_command_object.data)
                        dm.apply_shape(new_command, 1)

                        amplitude_path = os.path.join(iteration_path, "amplitude" + str(ampl_ptv))

                        testbed.run_hicat_imaging(auto_exposure_time, self.num_exposures, self.fpm_position,
                                                  lyot_stop_position=self.lyot_stop_position,
                                                  centering=self.centering,
                                                  path=amplitude_path, auto_exposure_time=False,
                                                  exposure_set_name=exp_set_name, filename="itr" + str(i) + "_" + name,
                                                  simulator=False, **self.kwargs)

                    # Run control on the set of phase shifted data.
                    new_amplitude_tmp = speckle_nulling.speckle_control_amplitude(iteration_path, exp_set_name)
                    new_amplitude = quantity(new_amplitude_tmp, units.nanometer)

                    # Create a new sine wave at the specified phase, and add it to our current_dm_command.
                    phase_correction_command = sin_command(SinSpecification(angle_deg_new, ncycles_new, new_amplitude,
                                                                            new_phase))
                    current_command_object.data += phase_correction_command.data

                # Take a final (non-saturated) image using auto exposure without the dark zone mask.
                testbed.run_hicat_imaging(self.exposure_time, self.num_exposures, self.fpm_position,
                                          centering=self.centering,
                                          lyot_stop_position=self.lyot_stop_position,
                                          path=self.path,
                                          exposure_set_name="final", filename="final_dark_zone.fits",
                                          simulator=False, **self.kwargs)
