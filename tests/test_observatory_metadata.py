import logging
import os
import unittest
import numpy as np
import pint.observatory


class TestObservatoryMetadata(unittest.TestCase):
    """ Test handling of observatory metadata"""

    @classmethod
    def setUpClass(cls):
        # name of an observatory that PINT should know about
        # and should have metadata on
        cls.pint_obsname = "gbt"
        # name of an observatory that only astropy should know about
        cls.astropy_obsname = "keck"

        cls.log = logging.getLogger("TestObservatoryMetadata")

    def test_astropy_observatory(self):
        """
        try to instantiate the observatory in PINT from astropy and check their metadata
        """
        keck = pint.observatory.get_observatory(self.astropy_obsname)
        msg = (
            "Checking PINT metadata for '%s' failed: 'astropy' not present in '%s'"
            % (self.astropy_obsname, keck.origin,)
        )
        assert "astropy" in keck.origin

    def test_pint_observatory(self):
        """
        try to instantiate the observatory in PINT  and check their metadata
        """
        gbt = pint.observatory.get_observatory(self.pint_obsname)
        msg = "Checking PINT definition for '%s' failed: metadata is '%s'" % (
            self.pint_obsname,
            gbt.origin,
        )
        assert (gbt.origin is not None) and (len(gbt.origin) > 0)

    def test_observatory_replacement(self):
        from pint.observatory.topo_obs import TopoObs

        TopoObs(
            "gbt",
            tempo_code="1",
            itoa_code="GB",
            itrf_xyz=[882589.65, -4924872.32, 3943729.348],
            origin="This is a test",
        )
        assert True
