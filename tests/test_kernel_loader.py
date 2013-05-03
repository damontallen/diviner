# coding: utf-8
import unittest
import os
import spice
from datetime import datetime as dt
from diviner.file_utils import kernelpath
from diviner import kerneltools

def test_example_loading():
    currentdir = os.getcwd()
    os.chdir(kernelpath)
    spice.furnsh("ck/moc42_2010100_2010101_v02.bc")
    spice.furnsh("fk/lro_frames_2012255_v02.tf")
    spice.furnsh("fk/lro_dlre_frames_2010132_v04.tf")
    spice.furnsh("ick/lrodv_2010090_2010121_v01.bc")
    spice.furnsh("lsk/naif0010.tls")
    spice.furnsh('sclk/lro_clkcor_2010096_v00.tsc')
    spice.furnsh("spk/fdf29_2010100_2010101_n01.bsp")
    spice.furnsh('./planet_spk/de421.bsp')

    utc = dt.strptime('2010100 10','%Y%j %H').isoformat()
    et = spice.utc2et(utc)
    t = spice.spkpos('sun',et,'LRO_DLRE_SCT_REF','lt+s','lro')
    answer = ((-63972935.85033857, -55036272.7848299, 123524941.9877458), 499.009424105693)
    for i,j in zip(t[0],answer[0]):
        assert round(i,3) == round(j,3)
    os.chdir(currentdir)
        
def test_load_for_time():
    pass
    
def test_get_version_from_fname():
    fname = 'moc42_2009099_2009100_v01.bc'
    version = 1
    assert version == kerneltools.get_version_from_fname(fname)
    
def test_get_times_from_ck_fname():
    fname = 'moc42_2009099_2009100_v01.bc'
    start_time = dt.strptime('2009099','%Y%j')
    end_time = dt.strptime('2009100','%Y%j')
    
if __name__ == '__main__':
    test_loading()