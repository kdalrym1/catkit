from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

# noinspection PyUnresolvedReferences
from builtins import *

from glob import glob
import logging

from ..Experiment import Experiment
from ...hardware.boston import commands
from ... import util
from ...hicat_types import units, quantity, ImageCentering
from ..modules.general import take_coffee_data_set
from hicat.hardware.boston import DmCommand


class CoffeeStrokeMin(Experiment):
    """
    Applies a command to DM1 coming from WL stroke min, and takes a COFFEE data set.

    Args:
        path (string): Path to save data set. None will use the default.
        num_exposures (int): Number of exposures.
        coron_exp_time (pint quantity): Exposure time for the coronographics data set.
        direct_exp_time (pint quantity): Exposure time for the direct PSF data set.
        centering (ImageCentering): Image centering algorithm for the coron data set.
        **kwargs: Keyword arguments passed into run_hicat_imaging()
    """

    name = "Coffee Stroke Min"
    log = logging.getLogger(__name__)

    def __init__(self,
                 path=None,
                 path_dm1_corr=None,
                 num_exposures=10,
                 coron_exp_time=quantity(100, units.millisecond),
                 direct_exp_time=quantity(1, units.millisecond),
                 centering=ImageCentering.custom_apodizer_spots,
                 **kwargs):
        self.path = path
        self.path_dm1_corr = path_dm1_corr
        self.num_exposures = num_exposures
        self.coron_exp_time = coron_exp_time
        self.direct_exp_time = direct_exp_time
        self.centering = centering
        self.kwargs = kwargs

    def experiment(self):
        if self.path is None:
            suffix = "coffee_strokemin"
            self.path = util.create_data_path(suffix=suffix)
            util.setup_hicat_logging(self.path, "coffee_strokemin")

        # Focus Zernike commands.
        focus_zernike_data_path = "Z:/Testbeds/hicat_dev/data_vault/coffee/coffee_commands/focus/"
        focus_zernike_command_paths = glob(focus_zernike_data_path + "/*p2v/*.fits")


        # DM1 correction, DM2 focus loop.
        dm1_path = self.path_dm1_corr
        dm1_correction = DmCommand.load_dm_command(dm1_path, flat_map=True, dm_num=1)
        take_coffee_data_set(focus_zernike_command_paths, self.path, "stroke_min", self.coron_exp_time,
                             self.direct_exp_time, num_exposures=self.num_exposures,
                             dm1_command_object=dm1_correction, centering=self.centering, **self.kwargs)
