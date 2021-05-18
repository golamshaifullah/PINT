"""Various tests to assess the performance of the DD model."""
import copy
import logging
import os
from io import StringIO
import unittest
import pytest

import astropy.units as u
import numpy as np

import pint.models.model_builder as mb
import pint.toa as toa
import test_derivative_utils as tdu
from pint.models.timing_model import TimingModelError, MissingParameter
from pint.residuals import Residuals
from pinttestdata import datadir


class TestDDK(unittest.TestCase):
    """Compare delays from the dd model with libstempo and PINT"""

    @classmethod
    def setUpClass(cls):
        os.chdir(datadir)
        cls.parfileJ1713 = "J1713+0747_NANOGrav_11yv0.gls.par"
        cls.timJ1713 = "J1713+0747_NANOGrav_11yv0_short.tim"
        cls.toasJ1713 = toa.get_TOAs(cls.timJ1713, ephem="DE421", planets=False)
        cls.toasJ1713.table.sort("index")
        cls.modelJ1713 = mb.get_model(cls.parfileJ1713)
        # libstempo result
        cls.ltres, cls.ltbindelay = np.genfromtxt(
            cls.parfileJ1713 + ".tempo_test", unpack=True
        )
        cls.temp_par_str = """PSR  J1713+0747
               LAMBDA 256.66  1 0.001
               BETA 30.70036  1 0.001
               PMLAMBDA 5.2671  1  0.0021
               PMBETA  -3.4428  1  0.0043
               PX  0.8211  1  0.0258
               F0  218.81  1  0.01
               PEPOCH  55391.0
               BINARY  DDK
               A1 32.34  1  0.001
               E  0.074  1  0.001
               T0 55388.836  1  0.0002
               PB 67.825129  1  0.0001
               OM 176.19845  1  0.0013
               M2  0.283395  1  0.0104
               KOM   83.100  1  1.800
               K96  1"""

    def test_J1713_binary_delay(self):
        # Calculate delays with PINT
        # NOTE tempo and PINT has different definition of parameter KOM. So lower the
        # threshold
        pint_binary_delay = self.modelJ1713.binarymodel_delay(self.toasJ1713, None)
        assert np.all(
            np.abs(pint_binary_delay.value + self.ltbindelay) < 5e-7
        ), "DDK J1713 TEST FAILED"

    def test_J1713(self):
        log = logging.getLogger("TestJ1713.test_J1713")
        pint_resids_us = Residuals(
            self.toasJ1713, self.modelJ1713, use_weighted_mean=False
        ).time_resids.to(u.s)
        diff = pint_resids_us.value - self.ltres
        log.debug("Max diff %lf" % np.abs(diff - diff.mean()).max())
        assert np.all(np.abs(diff - diff.mean()) < 5e-7), "DDK J1713 TEST FAILED"

    def test_J1713_deriv(self):
        log = logging.getLogger("TestJ1713.derivative_test")
        testp = tdu.get_derivative_params(self.modelJ1713)
        delay = self.modelJ1713.delay(self.toasJ1713)
        for p in testp.keys():
            # Only check the binary parameters
            if p not in self.modelJ1713.binary_instance.binary_params:
                continue
            if p in ["PX", "PMRA", "PMDEC"]:
                continue
            par = getattr(self.modelJ1713, p)
            if type(par).__name__ == "boolParameter":
                continue
            log.debug("Runing derivative for %s", "d_phase_d_" + p)
            ndf = self.modelJ1713.d_phase_d_param_num(self.toasJ1713, p, testp[p])
            adf = self.modelJ1713.d_phase_d_param(self.toasJ1713, delay, p)
            diff = adf - ndf
            if not np.all(diff.value) == 0.0:
                mean_der = (adf + ndf) / 2.0
                relative_diff = np.abs(diff) / np.abs(mean_der)
                # print "Diff Max is :", np.abs(diff).max()
                msg = (
                    "Derivative test failed at d_phase_d_%s with max relative difference %lf"
                    % (p, np.nanmax(relative_diff).value)
                )
                if p in ["SINI", "KIN"]:
                    tol = 0.7
                elif p in ["KOM"]:
                    tol = 0.04
                else:
                    tol = 1e-3
                log.debug(
                    "derivative relative diff for %s, %lf"
                    % ("d_phase_d_" + p, np.nanmax(relative_diff).value)
                )
                assert np.nanmax(relative_diff) < tol, msg
            else:
                continue

    def test_K96(self):
        modelJ1713 = copy.deepcopy(self.modelJ1713)
        log = logging.getLogger("TestJ1713 Switch of K96")
        modelJ1713.K96.value = False
        res = Residuals(
            self.toasJ1713, modelJ1713, use_weighted_mean=False
        ).time_resids.to(u.s)
        delay = self.modelJ1713.delay(self.toasJ1713)
        testp = tdu.get_derivative_params(modelJ1713)
        for p in testp.keys():
            self.modelJ1713.d_phase_d_param(self.toasJ1713, delay, p)

    def test_sini_from_value(self):
        modelJ1713 = copy.deepcopy(self.modelJ1713)
        modelJ1713.SINI.value = 0.9
        with pytest.raises(ValueError):
            modelJ1713.validate()

    def test_sini_from_par(self):
        test_par_str = self.temp_par_str + "\n SINI  0.8     1  0.562"
        with pytest.raises(ValueError):
            mb.get_model(StringIO(test_par_str))

    def test_stand_alone_model_params(self):
        test_par_str = self.temp_par_str + "\n KIN  71.969  1  0.562"
        m = mb.get_model(StringIO(test_par_str))
        for binary_par in m.binary_instance.binary_params:
            standalone_par = getattr(m.binary_instance, binary_par)
            try:
                pint_par_name = m.match_param_aliases(binary_par)
            except ValueError:
                if binary_par in m.internal_params:
                    pint_par_name = binary_par
                else:
                    pint_par_name = None
            if pint_par_name is None:
                continue
            pint_par = getattr(m, pint_par_name)
            if pint_par.value is not None:
                if hasattr(standalone_par, "value"):
                    assert pint_par.value == standalone_par.value
                else:
                    assert pint_par.value == standalone_par

    def test_zero_PX(self):
        zero_px_str = self.temp_par_str.replace("PX  0.8211", "PX  0.0")
        with pytest.raises(ValueError):
            m = mb.get_model(StringIO(zero_px_str))

    def test_remove_PX(self):
        test_par_str = self.temp_par_str + "\n KIN  71.969  1  0.562"
        m = mb.get_model(StringIO(test_par_str))
        m.remove_param("PX")
        with pytest.raises(MissingParameter):
            m.validate()


if __name__ == "__main__":
    pass
