import os

from catkit.catkit_types import FpmPosition, ImageCentering
import hicat.util
from hicat.hardware import testbed
from hicat.config import CONFIG_INI
from catkit.hardware.boston import commands
from catkit.hardware.boston import DmCommand


def take_coffee_data_set(dm2_command_list,
                         path,
                         exp_set_name,
                         coron_exp_time,
                         direct_exp_time,
                         num_exposures=10,
                         dm1_command_object=commands.flat_command(bias=False, flat_map=True),
                         camera_type="imaging_camera",
                         centering=ImageCentering.custom_apodizer_spots,
                         pipeline=True,
                         **kwargs):
    for command in dm2_command_list:
        dm2_command_object = DmCommand.load_dm_command(command, bias=False, flat_map=False, dm_num=2, as_volts=True)
        filename = os.path.basename(os.path.dirname(command))
        experiment_path = os.path.join(path, exp_set_name, filename)

        # Direct.
        take_exposures(dm1_command_object,
                       dm2_command_object,
                       direct_exp_time,
                       num_exposures,
                       camera_type,
                       False,
                       pipeline,
                       experiment_path,
                       filename,
                       "direct",
                       None,
                       centering=ImageCentering.psf,
                       **kwargs)

        # Coron.
        take_exposures(dm1_command_object,
                       dm2_command_object,
                       coron_exp_time,
                       num_exposures,
                       camera_type,
                       True,
                       pipeline,
                       experiment_path,
                       filename,
                       "coron",
                       None,
                       centering=centering,
                       **kwargs)


def take_exposures_both_dm_commands(dm2_command_list,
                                    dm1_command_list,
                                    path,
                                    exp_set_name,
                                    coron_exp_time,
                                    direct_exp_time,
                                    dm2_flat_map=False,
                                    dm1_flat_map=False,
                                    dm2_list_of_paths=True,
                                    dm1_list_of_paths=True,
                                    num_exposures=10,
                                    camera_type="imaging_camera",
                                    centering=ImageCentering.custom_apodizer_spots):

    for command1 in dm1_command_list:
        if dm1_list_of_paths:
            dm1_command_object = DmCommand.load_dm_command(command1, bias=False,
                                                           flat_map=dm1_flat_map,
                                                           dm_num=1, as_volts=True)
            filename1 = os.path.basename(command1).split('.')[0]
        else:
            dm1_command_object = command1
            filename1 = "flats"

        for command2 in dm2_command_list:
            if dm2_list_of_paths:
                dm2_command_object = DmCommand.load_dm_command(command2, bias=False,
                                                               flat_map=dm2_flat_map,
                                                               dm_num=2, as_volts=True)
                filename2 = os.path.basename(command2).split('.')[0]
            else:
                dm2_command_object = command2
                filename2 = "flat"
            experiment_path = os.path.join(path, exp_set_name, "dm1_{}_dm2_{}".format(filename1,
                                                                                      filename2))

            # Direct.
            take_exposures(dm1_command_object,
                           dm2_command_object,
                           direct_exp_time,
                           num_exposures,
                           camera_type,
                           False,
                           True,
                           experiment_path,
                           "dm1_{}_dm2_{}".format(filename1, filename2),
                           "direct",
                           suffix=None,
                           centering=ImageCentering.psf)

            # Coron.
            take_exposures(dm1_command_object,
                           dm2_command_object,
                           coron_exp_time,
                           num_exposures,
                           camera_type,
                           True,
                           True,
                           experiment_path,
                           "dm1_{}_dm2_{}".format(filename1, filename2),
                           "coron",
                           suffix=None,
                           centering=centering)


def take_exposures(dm1_command_object,
                   dm2_command_object,
                   exposure_time,
                   num_exposures,
                   camera_type,
                   coronograph,
                   pipeline,
                   path,
                   filename,
                   exposure_set_name,
                   suffix,
                   **kwargs):
    # Wait to set the path until the experiment starts (rather than the constructor)
    if path is None:
        suffix = "take_exposures_data" if suffix is None else "take_exposures_data_" + suffix
        path = hicat.util.create_data_path(suffix=suffix)

    hicat.util.setup_hicat_logging(path, "take_exposures_data")

    # Establish image type and set the FPM position and laser current
    if coronograph:
        fpm_position = FpmPosition.coron
        laser_current = CONFIG_INI.getint("thorlabs_source_mcls1", "coron_current")
        if exposure_set_name is None:
            exposure_set_name = "coron"
    else:
        fpm_position = FpmPosition.direct
        laser_current = CONFIG_INI.getint("thorlabs_source_mcls1", "direct_current")
        if exposure_set_name is None:
            exposure_set_name = "direct"

    # Take data
    with testbed.laser_source() as laser:
        laser.set_current(laser_current)

        with testbed.dm_controller() as dm:
            dm.apply_shape_to_both(dm1_command_object, dm2_command_object)
            return testbed.run_hicat_imaging(exposure_time, num_exposures, fpm_position,
                                             path=path,
                                             filename=filename,
                                             exposure_set_name=exposure_set_name,
                                             camera_type=camera_type,
                                             pipeline=pipeline,
                                             **kwargs)
