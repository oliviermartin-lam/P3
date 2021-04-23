#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 17 13:57:21 2021

@author: omartin
"""

import numpy as np
from aoSystem.optics import optics
from aoSystem.detector import detector
from aoSystem.processing import processing

class sensor:
    """
    Wavefront sensor class. This class is instantiated through three sub-classes:\
    optics, detector and processing.
    """
    
    def __init__(self,pixel_scale,fov,binning=1,spotFWHM=[0.0,0.0],\
                 nph=np.inf,bandwidth=0.0,transmittance=[1.0],dispersion=[[0.0],[0.0]],\
                 ron=0.0,gain=1.0,dark=0.0,sky=0.0,excess=1.0, \
                 wfstype='Shack-Hartmann',nL=[1],dsub=[1],nSides=None,modulation=None,\
                 algorithm='wcog', algo_param=[5,0,0], noiseVar=None, tag='SENSOR'):
        
                
        # optics class
        self.optics = optics(nL=nL,dsub=dsub,nSides=nSides,wfstype=wfstype,modulation=modulation)
        
        # detector class
        self.detector = detector(pixel_scale,fov,binning=binning,spotFWHM=spotFWHM,\
                 nph=nph,bandwidth=bandwidth,transmittance=transmittance,dispersion=dispersion,\
                 ron=ron,gain=gain,dark=dark,sky=sky,excess=excess)
        
        # processing class
        self.processing = processing(algorithm=algorithm,settings=algo_param,noiseVar=noiseVar)
        
    def NoiseVariance(self,r0,wvl):
        
        rad2arcsec = 3600 * 180 / np.pi

        # parsing inputs
        nph         = np.array(self.detector.nph)
        pixelScale  = self.detector.psInMas/1e3 # in arcsec
        ron         = self.detector.ron
        nPix        = self.detector.fovInPix/np.array(self.optics.nL)
        dsub        = self.optics.dsub
        
        # read-out noise calculation
        nD      = rad2arcsec * wvl/dsub/pixelScale #spot FWHM in pixels and without turbulence
        varRON  = np.pi**2/3*(ron**2 /nph**2) * (nPix**2/nD)**2
        
        if varRON.any() > 3:
            print('The read-out noise variance is very high (%.1f >3 rd^2), there is certainly smth wrong with your inputs, set to 0'%(varRON))
            varRON = 0
         
        # photo-noise calculation
        nT  = rad2arcsec*wvl/r0/pixelScale
        varShot  = np.pi**2/(2*nph)*(nT/nD)**2
        if varShot.any() > 3:
            print('The shot noise variance is very high (%.1f >3 rd^2), there is certainly smth wrong with your inputs, set to 0'%(varShot))
            varShot = 0
            
        return self.detector.excess * (varRON + varShot)