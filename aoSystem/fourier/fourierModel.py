#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 16:31:39 2020

@author: omartin
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 16 15:00:44 2018

@author: omartin
"""
import numpy as np
import matplotlib as mpl

import numpy.fft as fft
import matplotlib.pyplot as plt
import scipy.special as spc

import time
import os
import sys

from distutils.spawn import find_executable

import aoSystem.fourier.FourierUtils as FourierUtils
from aoSystem.aoSystem import aoSystem as aoSys
from aoSystem.atmosphere import atmosphere
from aoSystem.frequencyDomain import frequencyDomain as frequencyDomain

#%% DISPLAY FEATURES
mpl.rcParams['font.size'] = 16

if find_executable('tex'): 
    usetex = True
else:
    usetex = False

plt.rcParams.update({
    "text.usetex": usetex,
    "font.family": "serif",
    "font.serif": ["Palatino"],
})
 
#%%
rad2mas = 3600 * 180 * 1000 / np.pi
rad2arc = rad2mas / 1000
deg2rad = np.pi/180

def demoMavisPSD():
    # Instantiate the FourierModel class
    t0 = time.time()
    if sys.platform[0:3] == 'win':
        fao = fourierModel(os.getcwd()+"\parFile\mavisParams.ini",calcPSF=False,verbose=True,display=False,getErrorBreakDown=False)
    else:
        fao = fourierModel(os.getcwd()+"/parFile/mavisParams.ini",calcPSF=False,verbose=True,display=False,getErrorBreakDown=False)
    PSD = fao.powerSpectrumDensity()
    ttot = time.time() - t0
    print("Total calculation time - {:d} PSD (s)\t : {:f} ".format(fao.nSrc,ttot))
    return PSD

def demoMavisPSF():
    if sys.platform[0:3] == 'win':
        fao = fourierModel(os.getcwd()+"\parFile\mavisParams.ini",calcPSF=True,verbose=True,display=True,getErrorBreakDown=False)
    else:
        fao = fourierModel(os.getcwd()+"/parFile/mavisParams.ini",calcPSF=True,verbose=True,display=True,getErrorBreakDown=False)
    return fao

def demoHarmoniPSF():
    if sys.platform[0:3] == 'win':
        fao = fourierModel(os.getcwd()+"\parFile\harmoniParams.ini",calcPSF=True,verbose=True,display=True,\
                       getErrorBreakDown=True,getFWHM=True,getEncircledEnergy=True,getEnsquaredEnergy=False,displayContour=True)    
    else:
        fao = fourierModel(os.getcwd()+"/parFile/harmoniParams.ini",calcPSF=True,verbose=True,display=True,\
                       getErrorBreakDown=False,getFWHM=True,getEncircledEnergy=True,getEnsquaredEnergy=False,displayContour=True)    
    return fao

def demoHarmoniSCAOPSF():
    if sys.platform[0:3] == 'win':
        fao = fourierModel(os.getcwd()+"\parFile\harmoniSCAOParams.ini",calcPSF=True,verbose=True,display=True,\
                       getErrorBreakDown=False,getFWHM=False,getEncircledEnergy=False,getEnsquaredEnergy=False,displayContour=True)    
    else:
        fao = fourierModel(os.getcwd()+"/parFile/harmoniSCAOParams.ini",calcPSF=True,verbose=True,display=True,\
                       getErrorBreakDown=True,getFWHM=False,getEncircledEnergy=False,getEnsquaredEnergy=False,displayContour=False)    
    return fao
    
class fourierModel:
    """ Fourier class gathering the PSD calculation for PSF reconstruction. 
    """
    
    # CONTRUCTOR
    def __init__(self,path_ini,calcPSF=True,verbose=False,display=True,displayContour=False,\
                 getErrorBreakDown=False,getFWHM=False,getEnsquaredEnergy=False,\
                 getEncircledEnergy=False,fftphasor=False,MV=0):
        
        tstart = time.time()
        
        # PARSING INPUTS
        self.verbose           = verbose
        self.path_ini          = path_ini  
        self.display           = display
        self.getErrorBreakDown = getErrorBreakDown
        self.getPSFmetrics     = getFWHM or getEnsquaredEnergy or getEncircledEnergy
        self.calcPSF           = calcPSF
        
        # GRAB PARAMETERS
        self.ao = aoSys(path_ini)
        self.t_initAO = 1000*(time.time() - tstart)
        
        if self.ao.error==False:
            
            # DEFINING THE FREQUENCY DOMAIN
            self.freq = frequencyDomain(self.ao)
            
            # DEFINING THE GUIDE STAR AND THE STRECHING FACTOR
            if self.ao.lgs:
                self.gs  = self.ao.lgs
                self.nGs = self.ao.lgs.nSrc
                self.strechFactor = 1.0/(1.0 - self.ao.atm.heights/self.gs.heightGs[0])
            else:
                self.gs  = self.ao.ngs
                self.nGs = self.ao.ngs.nSrc
                self.strechFactor = 1.0
               
            # DEFINING THE NOISE AND ATMOSPHERE PSD
            if self.ao.wfs.processing.noiseVar == None:
                self.ao.wfs.processing.noiseVar = self.ao.wfs.NoiseVariance(self.ao.atm.r0 * (self.ao.atm.wvl/self.freq.wvlRef)**1.2 ,self.freq.wvlRef)
            
            self.Wn   = np.mean(self.ao.wfs.processing.noiseVar)/(2*self.freq.kcMin_)**2
            self.Wphi = self.ao.atm.spectrum(np.sqrt(self.freq.k2AO_));
            
            # DEFINING THE MODELED ATMOSPHERE 
            if (self.ao.dms.nRecLayers!=None) and (self.ao.dms.nRecLayers < len(self.ao.atm.weights)):
                weights_mod,heights_mod = FourierUtils.eqLayers(self.ao.atm.weights,self.ao.atm.heights,self.ao.dms.nRecLayers)
                wSpeed_mod = np.linspace(min(self.wSpeed),max(self.ao.atm.wSpeed),num=self.ao.dms.nRecLayers)
                wDir_mod   = np.linspace(min(self.ao.atm.wDir),max(self.ao.atm.wDir),num=self.ao.dms.nRecLayers)
            else:
                weights_mod    = self.ao.atm.weights
                heights_mod    = self.ao.atm.heights
                wSpeed_mod     = self.ao.atm.wSpeed
                wDir_mod       = self.ao.atm.wDir
            
            self.atm_mod = atmosphere(self.ao.atm.wvl,self.ao.atm.r0,weights_mod,heights_mod,wSpeed_mod,wDir_mod,self.ao.atm.L0)
            
            #updating the atmosphere wavelength !
            self.ao.atm.wvl  = self.freq.wvlRef
            self.atm_mod.wvl = self.freq.wvlRef
            self.t_initFreq = 1000*(time.time() - tstart)

            # DEFINE THE RECONSTRUCTOR
            self.spatialReconstructor(MV=MV)
                
            # DEFINE THE CONTROLLER
            self.controller()
                
            # COMPUTE THE PSD
            self.PSD = self.powerSpectrumDensity()
                
            if calcPSF:
                # COMPUTING THE PSF
                self.PSF, self.SR = self.pointSpreadFunction(verbose=verbose,fftphasor=fftphasor)
                
                # GETTING METRICS
                if getFWHM == True or getEnsquaredEnergy==True or getEncircledEnergy==True:
                    self.getPsfMetrics(getEnsquaredEnergy=getEnsquaredEnergy,\
                        getEncircledEnergy=getEncircledEnergy,getFWHM=getFWHM)
    
                # DISPLAYING THE PSFS
                if display:
                    self.displayResults(displayContour=displayContour)
              
            # COMPUTE THE ERROR BREAKDOWN
            if self.getErrorBreakDown:
                self.errorBreakDown()
                    
        self.t_init = 1000*(time.time()  - tstart)
        
        # DISPLAYING EXECUTION TIMES
        if verbose:
            self.displayExecutionTime()
          
        # DEFINING BOUNDS
        self.bounds = self.defineBounds()
            
    def __repr__(self):
        s = "Fourier Model class "
        if self.status == 1:
            s = s + "instantiated"
        else:
            s = s + "not instantiated"
        
        #self.displayResults()
        
        return s

#%% BOUNDS FOR PSF-FITTING
    def defineBounds(self):
          
        # Photometry
        bounds_down  = [-np.inf,-np.inf,-np.pi]
        bounds_up    = [np.inf,np.inf,np.pi]
        # Photometry
        bounds_down += list(np.zeros(self.ao.src.nSrc))
        bounds_up   += list(np.inf*np.ones(self.ao.src.nSrc))
        # Astrometry
        bounds_down += list(-self.freq.nPix//2 * np.ones(2*self.ao.src.nSrc))
        bounds_up   += list( self.freq.nPix//2 * np.ones(2*self.ao.src.nSrc))
        # Background
        bounds_down += [-np.inf]
        bounds_up   += [np.inf]
        
        return (bounds_down,bounds_up)
      
#%% RECONSTRUCTOR DEFINITION    
    def spatialReconstructor(self,MV=0):
        tstart  = time.time()
        
        if self.nGs <2:
            self.reconstructionFilter(MV=MV)
        else:
        
            self.Wtomo  = self.tomographicReconstructor()
            self.Popt   = self.optimalProjector()
            self.W      = np.matmul(self.Popt,self.Wtomo)
            
            # Computation of the Pbeta^DM matrix
            k       = np.sqrt(self.freq.k2_)
            h_dm    = self.ao.dms.heights
            nDm     = len(h_dm)
            nK      = self.freq.resAO
            i       = complex(0,1)
            nH      = self.ao.atm.nL
            Hs      = self.ao.atm.heights * self.strechFactor
            d       = self.freq.pitch[0]
            sampTime= self.ao.rtc.holoop['rate']
            
            self.PbetaDM = []
            for s in range(self.nSrc):
                fx = self.ao.src[s].direction[0]*self.freq.kxAO_
                fy = self.ao.src[s].direction[1]*self.freq.kyAO_
                PbetaDM = np.zeros([nK,nK,1,nDm],dtype=complex)
                for j in range(nDm): #loop on DMs
                    index               = k <= self.freq.kc_[j] # note : circular masking
                    PbetaDM[index,0,j]  = np.exp(2*i*np.pi*h_dm[j]*(fx[index] + fy[index]))
                self.PbetaDM.append(PbetaDM)
            
            # Computation of the Malpha matrix
            wDir_x  = np.cos(self.ao.atm.wDir*np.pi/180)
            wDir_y  = np.sin(self.ao.atm.wDir*np.pi/180)
            self.MPalphaL = np.zeros([nK,nK,self.nGs,nH],dtype=complex)
            for h in range(nH):
                www = np.sinc(sampTime*self.ao.atm.wSpeed[h]*(wDir_x[h]*self.freq.kxAO_ + wDir_y[h]*self.freq.kyAO_))
                for g in range(self.nGs):
                    Alpha = [self.gs[g].direction[0],self.gs[g].direction[1]]
                    fx = Alpha[0]*self.freq.kxAO_
                    fy = Alpha[1]*self.freq.kyAO_
                    self.MPalphaL[:,:,g,h] = www*2*i*np.pi*k*np.sinc(d*self.freq.kxAO_)*\
                        np.sinc(d*self.freq.kyAO_)*np.exp(i*2*np.pi*Hs[h]*(fx+fy))
                
            self.Walpha = np.matmul(self.W,self.MPalphaL)
            
        self.t_finalReconstructor = 1000*(time.time() - tstart)
           
    def reconstructionFilter(self,MV=0):
        """
        """          
        tstart = time.time()
        # reconstructor derivation
        i           = complex(0,1)
        d           = self.ao.wfs.optics.dsub[0]
       
        if self.ao.wfs.optics.wfstype.upper() == 'SHACK-HARTMANN':
            Sx      = 2*i*np.pi*self.freq.kxAO_*d
            Sy      = 2*i*np.pi*self.freq.kyAO_*d                        
            Av      = np.sinc(d*self.freq.kxAO_)*np.sinc(d*self.freq.kyAO_)*np.exp(i*np.pi*d*(self.freq.kxAO_ + self.freq.kyAO_))      
            
        elif self.ao.wfs.optics.wfstype.upper() == 'PYRAMID':
            # forward pyramid filter (continuous) from Conan
            umod    = 1/(2*d)/(self.ao.wfs.optics.nL[0]/2)*self.ao.wfs.optics.modulation
            Sx      = np.zeros((self.freq.resAO,self.freq.resAO),dtype=complex)
            idx     = abs(self.freq.kxAO_) > umod
            Sx[idx] = i*np.sign(self.freq.kxAO_[idx])
            idx     = abs(self.freq.kxAO_) <= umod
            Sx[idx] = 2*i/np.pi*np.arcsin(self.freq.kxAO_[idx]/umod)
            Av      = np.sinc(self.ao.wfs.detector.binning*d*self.freq.kxAO_)*np.sinc(self.ao.wfs.detector.binning*d*self.freq.kxAO_).T
            Sy      = Sx.T
            
        self.SxAv  = Sx*Av
        self.SyAv  = Sy*Av
        # MMSE
        wvlGs = self.gs.wvl
            
        Watm       = self.ao.atm.spectrum(np.sqrt(self.freq.k2AO_)) * (self.ao.atm.wvl/wvlGs) ** 2
        gPSD       = abs(self.SxAv)**2 + abs(self.SyAv)**2 + MV*self.Wn/Watm
        self.Rx    = np.conj(self.SxAv)/gPSD
        self.Ry    = np.conj(self.SyAv)/gPSD
        
        # Manage NAN value if any   
        self.Rx[np.isnan(self.Rx)] = 0
        self.Ry[np.isnan(self.Ry)] = 0
        
        # Set central point (i.e. kx=0,ky=0) to zero
        N = int(np.ceil((self.freq.kxAO_.shape[0]-1)/2))
        self.Rx[N,N] = 0
        self.Ry[N,N] = 0
            
        self.t_reconstructor = 1000*(time.time()  - tstart)
        
    def tomographicReconstructor(self):
        
        tstart  = time.time()
        k       = np.sqrt(self.freq.k2_)
        nK      = self.resAO
        nL      = len(self.ao.atm.heights)
        h_mod   = self.atm_mod.heights * self.strechFactor
        nL_mod  = len(h_mod)
        nGs     = self.nGs
        i       = complex(0,1)
        d       = self.ao.wfs.lenslets.size   #sub-aperture size      
        
         # WFS operator and projection matrices
        M     = np.zeros([nK,nK,nGs,nGs],dtype=complex)
        P     = np.zeros([nK,nK,nGs,nL_mod],dtype=complex)         
        for j in range(nGs):
            M[:,:,j,j] = 2*i*np.pi*k*np.sinc(d[j]*self.freq.kxAO_)*np.sinc(d[j]*self.freq.kyAO_)
            for n in range(nL_mod):
                P[:,:,j,n] = np.exp(i*2*np.pi*h_mod[n]*(self.freq.kxAO_*self.gs[j].direction[0] + self.freq.kyAO_*self.gs[j].direction[1]))
        self.M = M
        MP = np.matmul(self.M,P)
        MP_t = np.conj(MP.transpose(0,1,3,2))
        
        # Noise covariance matrix
        self.Cb = np.ones((nK,nK,nGs,nGs))*np.diag(self.ao.wfs.processing.noiseVar)
        
        # Atmospheric PSD with the true atmosphere
        self.Cphi   = np.zeros([nK,nK,nL,nL],dtype=complex)
        cte         = (24*spc.gamma(6/5)/5)**(5/6)*(spc.gamma(11/6)**2./(2.*np.pi**(11/3)))
        kernel      = self.ao.atm.r0**(-5/3)*cte*(self.freq.k2_ + 1/self.ao.atm.L0**2)**(-11/6)*self.freq.pistonFilterAO_
        self.Cphi   = kernel.repeat(nL**2,axis=1).reshape((nK,nK,nL,nL))*np.diag(self.ao.atm.weights)
        
        # Atmospheric PSD with the modelled atmosphere
        if nL_mod == nL:
            self.Cphi_mod = self.Cphi
        else:
            self.Cphi_mod = kernel.repeat(nL_mod**2,axis=1).reshape((nK,nK,nL_mod,nL_mod))*np.diag(self.atm_mod.weights)
        to_inv  = np.matmul(np.matmul(MP,self.Cphi_mod),MP_t) + self.Cb 
        
        # Wtomo
        inv = np.linalg.pinv(to_inv,rcond=1/self.condmax_tomo)
        Wtomo = np.matmul(np.matmul(self.Cphi_mod,MP_t),inv)        
        self.t_tomo = 1000*(time.time() - tstart)
        
        return Wtomo
 
    def optimalProjector(self):
        
        tstart = time.time()
        k       = np.sqrt(self.freq.k2_)
        h_dm    = self.ao.dms.heights
        nDm     = len(h_dm)
        nDir    = (len(self.ao.dms.opt_dir[0]))
        h_mod   = self.atm_mod.heights * self.strechFactor
        nL      = len(h_mod)
        nK      = self.freq.resAO
        i       = complex(0,1)
        
        mat1    = np.zeros([nK,nK,nDm,nL],dtype=complex)
        to_inv  = np.zeros([nK,nK,nDm,nDm],dtype=complex)
        theta_x = self.ao.dms.opt_dir[0]/206264.8 * np.cos(self.ao.dms.opt_dir[1]*np.pi/180)
        theta_y = self.ao.dms.opt_dir[0]/206264.8 * np.sin(self.ao.dms.opt_dir[1]*np.pi/180)
        
        for d_o in range(nDir):                 #loop on optimization directions
            Pdm = np.zeros([nK,nK,1,nDm],dtype=complex)
            Pl  = np.zeros([nK,nK,1,nL],dtype=complex)
            fx  = theta_x[d_o]*self.freq.kxAO_
            fy  = theta_y[d_o]*self.freq.kyAO_
            for j in range(nDm):                # loop on DM
                index   = k <= self.freq.kc_[j] # note : circular masking here
                Pdm[index,0,j] = np.exp(i*2*np.pi*h_dm[j]*(fx[index]+fy[index]))
            Pdm_t = np.conj(Pdm.transpose(0,1,3,2))
            for l in range(nL):                 #loop on atmosphere layers
                Pl[:,:,0,l] = np.exp(i*2*np.pi*h_mod[l]*(fx + fy))
                
            mat1   += np.matmul(Pdm_t,Pl)*self.ao.dms.opt_weights[d_o]
            to_inv += np.matmul(Pdm_t,Pdm)*self.ao.dms.opt_weights[d_o]
            
        # Popt
        mat2 = np.linalg.pinv(to_inv,rcond=1/self.ao.dms.condmax_popt)
        Popt = np.matmul(mat2,mat1)
        
        self.t_opt = 1000*(time.time() - tstart)
        return Popt
 
    
#%% CONTROLLER DEFINITION
    def controller(self,nTh=1,nF=1000):
        """
        """
        tstart  = time.time()
        
        if self.ao.rtc.holoop['gain'] != 0:     
        
            i           = complex(0,1)
            vx          = self.ao.atm.wSpeed*np.cos(self.ao.atm.wDir*np.pi/180)
            vy          = self.ao.atm.wSpeed*np.sin(self.ao.atm.wDir*np.pi/180)   
            nPts        = self.freq.resAO
            thetaWind   = np.linspace(0, 2*np.pi-2*np.pi/nTh,nTh)
            costh       = np.cos(thetaWind)
            weights     = self.ao.atm.weights
            Ts          = 1.0/self.ao.rtc.holoop['rate']#samplingTime
            delay       = self.ao.rtc.holoop['delay']#latency        
            loopGain    = self.ao.rtc.holoop['gain']
            #delay       = np.floor(td/Ts)
                       
            # Instantiation
            h1          = np.zeros((nPts,nPts),dtype=complex)
            h2          = np.zeros((nPts,nPts))
            hn          = np.zeros((nPts,nPts))
            
            # Get the noise propagation factor
            f           = np.logspace(-3,np.log10(0.5/Ts),nF)
            z           = np.exp(-2*i*np.pi*f*Ts)
            self.hInt   = loopGain/(1.0 - z**(-1.0))
            self.rtfInt = 1.0/(1 + self.hInt * z**(-delay))
            self.atfInt = self.hInt * z**(-delay) * self.rtfInt
            
            if loopGain == 0:
                self.ntfInt = 1
            else:
                self.ntfInt = self.atfInt/z
                    
            self.noiseGain = np.trapz(abs(self.ntfInt)**2,f)*2*Ts
                 
            # Get transfer functions                                        
            for l in range(self.ao.atm.nL):
                h1buf = np.zeros((nPts,nPts,nTh),dtype=complex)
                h2buf = np.zeros((nPts,nPts,nTh))
                hnbuf = np.zeros((nPts,nPts,nTh))
                for iTheta in range(nTh):
                    fi      = -vx[l]*self.freq.kxAO_*costh[iTheta] - vy[l]*self.freq.kyAO_*costh[iTheta]
                    z       = np.exp(-2*i*np.pi*fi*Ts)
                    hInt    = loopGain/(1.0 - z**(-1.0))
                    rtfInt  = 1.0/(1.0 + hInt * z**(-delay))
                    atfInt  = hInt * z**(-delay) * rtfInt
                    
                    # AO transfer function
                    h2buf[:,:,iTheta] = abs(atfInt)**2
                    h1buf[:,:,iTheta] = atfInt
                    # noise transfer function
                    if loopGain == 0:
                        ntfInt = 1
                    else:
                        ntfInt = atfInt/z
                    hnbuf[:,:,iTheta] = abs(ntfInt)**2
                    
                h1 += weights[l]*np.sum(h1buf,axis=2)/nTh
                h2 += weights[l]*np.sum(h2buf,axis=2)/nTh
                hn += weights[l]*np.sum(hnbuf,axis=2)/nTh
            
            self.h1 = h1
            self.h2 = h2
            self.hn = hn
            
            if self.display:
                plt.figure()
                plt.semilogx(f,10*np.log10(abs(self.rtfInt)**2),label='Rejection transfer function')
                plt.semilogx(f,10*np.log10(abs(self.ntfInt)**2),label='Noise transfer function')
                plt.semilogx(f,10*np.log10(abs(self.atfInt)**2),label='Aliasing transfer function')
                plt.xlabel('Temporal frequency (Hz)')
                plt.ylabel('Magnitude (dB)')
                plt.legend()
            
        self.t_controller = 1000*(time.time() - tstart)
      
 #%% PSD DEFINTIONS  

    def powerSpectrumDensity(self):
        """ Total power spectrum density in nm^2.m^2
        """
        tstart  = time.time()
        
        dk     = 2*self.freq.kc_/self.freq.resAO
        rad2nm = self.ao.atm.wvl*1e9/2/np.pi
        
        if self.ao.rtc.holoop['gain'] == 0:            
            # OPEN-LOOP
            k   = np.sqrt(self.freq.k2_)
            pf  = FourierUtils.pistonFilter(self.ao.tel.D,k)
            psd = self.ao.atm.spectrum(k) * pf
            psd = psd[:,:,np.newaxis]
        else:
            # CLOSED-LOOP
            psd = np.zeros((self.freq.nOtf,self.freq.nOtf,self.ao.src.nSrc))
            
            # AO correction area
            id1 = np.ceil(self.freq.nOtf/2 - self.freq.resAO/2).astype(int)
            id2 = np.ceil(self.freq.nOtf/2 + self.freq.resAO/2).astype(int)
            
            # Noise
            self.psdNoise = np.real(self.noisePSD())       
            if self.nGs == 1:
                psd[id1:id2,id1:id2,:] = np.repeat(self.psdNoise[:, :, np.newaxis], self.ao.src.nSrc, axis=2)
            else:
                psd[id1:id2,id1:id2,:] = self.psdNoise
                
            # Aliasing
            self.psdAlias           = np.real(self.aliasingPSD())
            psd[id1:id2,id1:id2,:]  = psd[id1:id2,id1:id2,:] + np.repeat(self.psdAlias[:, :, np.newaxis], self.ao.src.nSrc, axis=2)
            
            # Differential refractive anisoplanatism
            self.psdDiffRef         = self.differentialRefractionPSD()
            psd[id1:id2,id1:id2,:]  = psd[id1:id2,id1:id2,:] + self.psdDiffRef
        
            # Chromatism
            self.psdChromatism      = self.chromatismPSD()
            psd[id1:id2,id1:id2,:]  = psd[id1:id2,id1:id2,:] + self.psdChromatism
        
            # Add the noise and spatioTemporal PSD
            self.psdSpatioTemporal = np.real(self.spatioTemporalPSD())
            psd[id1:id2,id1:id2,:] = psd[id1:id2,id1:id2,:] + self.psdSpatioTemporal
           
            # Fitting
            self.psdFit = np.real(self.fittingPSD())
            psd += np.repeat(self.psdFit[:, :, np.newaxis], self.ao.src.nSrc, axis=2)
            
        self.t_powerSpectrumDensity = 1000*(time.time() - tstart)
            
        # Return the 3D PSD array in nm^2.m^2
        return psd * (dk * rad2nm)**2
    
    def fittingPSD(self):
        """ Fitting error power spectrum density """                 
        tstart  = time.time()
        #Instantiate the function output
        psd                 = np.zeros((self.freq.nOtf,self.freq.nOtf))
        psd[self.freq.mskOut_]   = self.ao.atm.spectrum(np.sqrt(self.freq.k2_[self.freq.mskOut_]))
        self.t_fittingPSD = 1000*(time.time() - tstart)
        return psd
               
    def aliasingPSD(self):
        """ Aliasing error power spectrum density """ 
        
        tstart  = time.time()
        psd = np.zeros((self.freq.resAO,self.freq.resAO))
        i  = complex(0,1)
        d  = self.ao.wfs.optics.dsub[0]
        T  = 1.0/self.ao.rtc.holoop['rate']
        td = T * self.ao.rtc.holoop['delay']        
        vx = self.ao.atm.wSpeed*np.cos(self.ao.atm.wDir*np.pi/180)
        vy = self.ao.atm.wSpeed*np.sin(self.ao.atm.wDir*np.pi/180)
        weights = self.ao.atm.weights  
        w = 2*i*np.pi*d

        if hasattr(self, 'Rx') == False:
            self.reconstructionFilter()
        Rx = self.Rx*w
        Ry = self.Ry*w
        
        if self.ao.rtc.holoop['gain'] == 0:
            tf = 1
        else:
            tf = self.h1
            
        # loops on frequency shifts
        for mi in range(-self.freq.nTimes,self.freq.nTimes):
            for ni in range(-self.freq.nTimes,self.freq.nTimes):
                if (mi!=0) | (ni!=0):
                    km   = self.freq.kxAO_ - mi/d
                    kn   = self.freq.kyAO_ - ni/d
                    PR   = FourierUtils.pistonFilter(self.ao.tel.D,np.hypot(km,kn),fm=mi/d,fn=ni/d)
                    W_mn = (km**2 + kn**2 + 1/self.ao.atm.L0**2)**(-11/6)     
                    Q    = (Rx*km + Ry*kn) * (np.sinc(d*km)*np.sinc(d*kn))
                    avr  = 0
                        
                    for l in range(self.ao.atm.nL):
                        avr = avr + weights[l]* (np.sinc(km*vx[l]*T)*np.sinc(kn*vy[l]*T)
                        *np.exp(2*i*np.pi*km*vx[l]*td)*np.exp(2*i*np.pi*kn*vy[l]*td)*tf)
                                                          
                    psd = psd + PR*W_mn * abs(Q*avr)**2
        
        self.t_aliasingPSD = 1000*(time.time() - tstart)
        return self.freq.mskInAO_ * psd*self.ao.atm.r0**(-5/3)*0.0229 
    
    def noisePSD(self):
        """Noise error power spectrum density
        """
        tstart  = time.time()
        psd     = np.zeros((self.freq.resAO,self.freq.resAO))
        if self.ao.wfs.processing.noiseVar[0] > 0:
            if self.nGs < 2:        
                psd = abs(self.Rx**2 + self.Ry**2)
                psd = psd/(2*self.freq.kcMin_)**2
                psd = self.freq.mskInAO_ * psd * self.freq.pistonFilterAO_
            else:  
                psd = np.zeros((self.freq.resAO,self.freq.resAO,self.nSrc),dtype=complex)
                #where is the noise level ?
                for j in range(self.ao.src.nSrc):
                    PW      = np.matmul(self.PbetaDM[j],self.W)
                    PW_t    = np.conj(PW.transpose(0,1,3,2))
                    tmp     = np.matmul(PW,np.matmul(self.Cb,PW_t))
                    psd[:,:,j] = self.freq.mskInAO_ * tmp[:,:,0,0]*self.freq.pistonFilterAO_
        
        self.t_noisePSD = 1000*(time.time() - tstart)
        # NOTE: the noise variance is the same for all WFS
        return  psd*self.noiseGain * np.mean(self.ao.wfs.processing.noiseVar)
    
    def servoLagPSD(self):
        """ Servo-lag power spectrum density
        """
        tstart  = time.time()    
        psd = np.zeros((self.freq.resAO,self.freq.resAO))    
        if hasattr(self, 'Rx') == False:
            self.reconstructionFilter()

        F = self.Rx*self.SxAv + self.Ry*self.SyAv     
        Watm = self.Wphi * self.freq.pistonFilterAO_       
        if (self.ao.rtc.holoop['gain'] == 0):
            psd = abs(1-F)**2 * Watm
        else:
            psd = (1.0 + abs(F)**2*self.h2 - 2*np.real(F*self.h1))*Watm
        
        self.t_servoLagPSD = 1000*(time.time() - tstart)
        return self.freq.mskInAO_ * psd
    
    def spatioTemporalPSD(self):
        """%% Power spectrum density including reconstruction, field variations and temporal effects
        """
        tstart  = time.time()   
        nK  = self.freq.resAO
        psd = np.zeros((nK,nK,self.ao.src.nSrc),dtype=complex)        
        i   = complex(0,1)
        nH  = self.ao.atm.nL
        Hs  = self.ao.atm.heights * self.strechFactor
        Ws  = self.ao.atm.weights
        deltaT  = (1+self.ao.rtc.holoop['delay'])/self.ao.rtc.holoop['rate']
        wDir_x  = np.cos(self.ao.atm.wDir*np.pi/180)
        wDir_y  = np.sin(self.ao.atm.wDir*np.pi/180)
        Watm = self.Wphi * self.freq.pistonFilterAO_      
        F = self.Rx*self.SxAv + self.Ry*self.SyAv
        
        for s in range(self.ao.src.nSrc):
            if self.nGs < 2:  
                th  = self.ao.src.direction[:,s] - self.gs.direction[:,0]
                if np.any(th):
                    A = np.zeros((nK,nK))
                    for l in range(self.atm.nL):                
                        A   = A + Ws[l]*np.exp(2*i*np.pi*Hs[l]*(self.kx*th[1] + self.ky*th[0]))            
                else:
                    A = np.ones((self.freq.resAO,self.freq.resAO))
          
                if (self.ao.rtc.holoop['gain'] == 0):  
                    psd[:,:,s] = abs(1-F)**2 * Watm
                else:
                    psd[:,:,s] = self.freq.mskInAO_ * (1 + abs(F)**2*self.h2 - 2*np.real(F*self.h1*A))*Watm                   
            else:    
                # tomographic case
                Beta = [self.ao.src[s].direction[0],self.ao.src[s].direction[1]]
                PbetaL = np.zeros([nK,nK,1,nH],dtype=complex)
                fx = Beta[0]*self.kx
                fy = Beta[1]*self.ky
                for j in range(nH):
                    PbetaL[:,:,0,j] = np.exp(i*2*np.pi*( Hs[j]*\
                          (fx+fy) -  deltaT*self.ao.atm.wSpeed[j]\
                          *(wDir_x[j]*self.kx+ wDir_y[j]*self.ky)))
   

                proj    = PbetaL - np.matmul(self.PbetaDM[s],self.Walpha)            
                proj_t  = np.conj(proj.transpose(0,1,3,2))
                tmp     = np.matmul(proj,np.matmul(self.Cphi,proj_t))
                psd[:,:,s] = self.freq.mskInAO_ * tmp[:,:,0,0]*self.freq.pistonFilterAO_
        self.t_spatioTemporalPSD = 1000*(time.time() - tstart)
        return psd
    
    def anisoplanatismPSD(self):
        """%% Anisoplanatism power spectrum density
        """
        tstart  = time.time()
        psd = np.zeros((self.freq.resAO,self.freq.resAO,self.ao.src.nSrc))
        Hs = self.ao.atm.heights * self.strechFactor
        Ws = self.ao.atm.weights
        Watm = self.Wphi * self.freq.pistonFilterAO_       
        
        for s in range(self.ao.src.nSrc):
            th  = self.ao.src.direction[:,s] - self.gs.direction[:,0]
            if any(th):
                A = np.zeros((self.freq.resAO,self.freq.resAO))
                for l in range(self.ao.atm.nL):
                    A   = A + 2*Ws[l]*(1 - np.cos(2*np.pi*Hs[l]*(self.freq.kx*th[1] + self.freq.ky*th[0])))             
                psd[:,:,s] = A*Watm
        self.t_anisoplanatismPSD = 1000*(time.time() - tstart)
        return self.freq.mskInAO_ * np.real(psd)
    
    def tomographyPSD(self):
        """%% Tomographic error power spectrum density - TO BE REVIEWED
        """
        tstart  = time.time()
        k       = np.sqrt(self.freq.k2_)
        nK      = self.freq.resAO
        psd     = np.zeros((nK,nK))
        deltaT  = (1+self.ao.rtc.holoop['delay'])/self.ao.rtc.holoop['rate']
        nH      = self.ao.atm.nL
        Hs      = self.ao.atm.heights * self.strechFactor
        i       = complex(0,1)
        d       = self.pitchs_dm[0]
        wDir_x  = np.cos(self.ao.atm.wDir*np.pi/180)
        wDir_y  = np.sin(self.ao.atm.wDir*np.pi/180)
        sampTime= 1/self.ao.rtc.holoop['rate']
        s       = 0
        Beta = [self.ao.src[s].direction[0],self.ao.src[s].direction[1]]
            
        MPalphaL = np.zeros([nK,nK,self.nGs,nH],dtype=complex)
        for h in range(nH):
            www = np.sinc(sampTime*self.ao.atm.wSpeed[h]*(wDir_x[h]*self.freq.kx + wDir_y[h]*self.freq.ky))
            for g in range(self.nGs):
                Alpha = [self.gs[g].direction[0],self.gs[g].direction[1]]
                fx = Alpha[0]*self.freq.kx
                fy = Alpha[1]*self.freq.ky
                MPalphaL[:,:,g,h] = www*2*i*np.pi*k*np.sinc(d*self.freq.kx)\
                *np.sinc(d*self.freq.ky)*np.exp(i*2*np.pi*Hs[h]*(fx+fy))
            
        PbetaL = np.zeros([nK,nK,1,nH],dtype=complex)
        fx = Beta[0]*self.freq.kx
        fy = Beta[1]*self.freq.ky
        for j in range(nH):
            PbetaL[:,:,0,j] = np.exp(i*2*np.pi*( Hs[j]*\
                  (fx+fy) -  \
                  deltaT*self.ao.atm.wSpeed[j]*(wDir_x[j]*self.freq.kx + wDir_y[j]*self.freq.ky) ))
            
        W       = self.W
        Cphi    = self.Cphi # PSD obtained from the true atmosphere
            
        # this calculation is not ok !!
        proj    = PbetaL - np.matmul(W,MPalphaL)           
        proj_t  = np.conj(proj.transpose(0,1,3,2))
        psd     = np.matmul(proj,np.matmul(Cphi,proj_t))
        psd     = self.freq.mskInAO_ * psd[:,:,0,0]
        self.t_tomographyPSD = 1000*(time.time() - tstart)
        return psd*self.freq.pistonFilterAO_
    
    def differentialRefractionPSD(self):
        def refractionIndex(wvl,nargout=1):
            ''' Refraction index -1 as a fonction of the wavelength. 
            Valid for lambda between 0.2 and 4µm with 1 atm of pressure and 15 degrees Celsius
                Inputs : wavelength in meters
                Outputs : n-1 and dn/dwvl
            '''
            c1 = 64.328
            c2 = 29498.1
            c3 = 146.0
            c4 = 255.4
            c5 = 41.0
            wvlRef = wvl*1e6
            
            nm1 = 1e-6 * (c1 +  c2/(c3-1.0/wvlRef**2) + c4/(c5 - 1.0/wvlRef**2) )
            dndw= -2e-6 * (c1 +  c2/(c3-1.0/wvlRef**2)**2 + c4/(c5 - 1.0/wvlRef**2)**2 )/wvlRef**3
            if nargout == 1:
                return nm1    
            else:
                return (nm1,dndw)
            
        def refractiveAnisoplanatism(zenithAngle,wvl):
            ''' Calculate the angular shift due to the atmospheric refraction at wvl
            and for a zenith angle zenithAngle in rad
            '''
            return refractionIndex(wvl) * np.tan(zenithAngle)
        
        def differentialRefractiveAnisoplanatism(zenithAngle,wvlGs,wvlSrc):
            return (refractionIndex(wvlSrc) - refractionIndex(wvlGs)) * np.tan(zenithAngle)
    
        tstart  = time.time()
        
        psd= np.zeros((self.freq.resAO,self.freq.resAO,self.ao.src.nSrc))
        if self.ao.tel.zenith_angle != 0:
            Hs   = self.ao.atm.heights * self.strechFactor
            Ws   = self.ao.atm.weights
            Watm = self.Wphi * self.freq.pistonFilterAO_     
            A    = 0
            k    = np.sqrt(self.freq.k2_)
            arg_k= np.arctan2(self.freq.kyAO_,self.freq.kxAO_)
            azimuth = self.ao.src.azimuth
        
        
            for s in range(self.ao.src.nSrc):
                theta = differentialRefractiveAnisoplanatism(self.ao.tel.zenith_angle*np.pi/180,self.gs.wvl[0], self.freq.wvl[s])
                for l in range(self.ao.atm.nL):
                    A   = A + 2*Ws[l]*(1 - np.cos(2*np.pi*Hs[l]*k*np.tan(theta)*np.cos(arg_k-azimuth)))            
                psd[:,:,s] = self.freq.mskInAO_ *A*Watm
         
        self.t_differentialRefractionPSD = 1000*(time.time() - tstart)
        return  psd
      
    def chromatismPSD(self):
        """ PSD of the chromatic effects"""
        tstart  = time.time()
        Watm = self.Wphi * self.freq.pistonFilterAO_   
        psd= np.zeros((self.freq.resAO,self.freq.resAO,self.ao.src.nSrc))
        n2 =  23.7+6839.4/(130-(self.gs.wvl*1.e6)**(-2))+45.47/(38.9-(self.gs.wvl*1.e6)**(-2))
        for s in range(self.ao.src.nSrc):
            n1 =  23.7+6839.4/(130-(self.freq.wvl[s]*1.e6)**(-2))+45.47/(38.9-(self.freq.wvl[s]*1.e6)**(-2))     
            psd[:,:,s] = ((n2-n1)/n2)**2 * Watm
       
        self.t_chromatismPSD = 1000*(time.time() - tstart)
        return psd
    
    
    #%% AO ERROR BREAKDOWN
    def errorBreakDown(self):
        """ AO error breakdown from the PSD integrals
        """        
        tstart  = time.time()
        
        if self.ao.rtc.holoop['gain'] != 0:
            # Derives wavefront error
            rad2nm      = (2*self.freq.kc_/self.freq.resAO) * self.freq.wvlRef*1e9/2/np.pi
            
            if np.any(self.ao.tel.opdMap_ext):
                self.wfeNCPA= np.std(self.ao.tel.opdMap_ext[self.ao.tel.pupil!=0])
            else:
                self.wfeNCPA = 0.0
                
            self.wfeFit    = np.sqrt(self.psdFit.sum()) * rad2nm
            self.wfeAl     = np.sqrt(self.psdAlias.sum()) * rad2nm
            self.wfeN      = np.sqrt(self.psdNoise.sum(axis=(0,1)))* rad2nm
            self.wfeST     = np.sqrt(self.psdSpatioTemporal.sum(axis=(0,1)))* rad2nm
            self.wfeDiffRef= np.sqrt(self.psdDiffRef.sum(axis=(0,1)))* rad2nm
            self.wfeChrom  = np.sqrt(self.psdChromatism.sum(axis=(0,1)))* rad2nm
            self.wfeJitter = 1e9*self.ao.tel.D*np.mean(self.ao.wfs.detector.spotFWHM[0:1])/rad2mas/4
            
            # Total wavefront error
            self.wfeTot = np.sqrt(self.wfeNCPA**2 + self.wfeFit**2 + self.wfeAl**2\
                                  + self.wfeST**2 + self.wfeN**2 + self.wfeDiffRef**2\
                                  + self.wfeChrom**2 + self.wfeJitter**2)
            
            # Maréchal appoximation to ge tthe Strehl-ratio
            self.SRmar  = 100*np.exp(-(self.wfeTot*2*np.pi*1e-9/self.freq.wvl)**2)
            
            # bonus
            self.psdS = self.servoLagPSD()
            self.wfeS = np.sqrt(self.psdS.sum()) * rad2nm
            if self.nGs == 1:
                self.psdAni = self.anisoplanatismPSD()
                self.wfeAni = np.sqrt(self.psdAni.sum(axis=(0,1))) * rad2nm
            else:
                self.wfeTomo = np.sqrt(self.wfeST**2 - self.wfeS**2)
                    
            # Print
            if self.verbose == True:
                print('\n_____ ERROR BREAKDOWN  ON-AXIS_____')
                print('------------------------------------------')
                idCenter = self.ao.src.zenith.argmin()
                if hasattr(self,'SR'):
                    print('.Image Strehl at %4.2fmicron:\t%4.2f%s'%(self.freq.wvlRef*1e6,self.SR[idCenter,0],'%'))
                print('.Maréchal Strehl at %4.2fmicron:\t%4.2f%s'%(self.ao.atm.wvl*1e6,self.SRmar[idCenter],'%'))
                print('.Residual wavefront error:\t%4.2fnm'%self.wfeTot[idCenter])
                print('.NCPA residual:\t\t\t%4.2fnm'%self.wfeNCPA)
                print('.Fitting error:\t\t\t%4.2fnm'%self.wfeFit)
                print('.Differential refraction:\t%4.2fnm'%self.wfeDiffRef[idCenter])
                print('.Chromatic error:\t\t%4.2fnm'%self.wfeChrom[idCenter])
                print('.Aliasing error:\t\t%4.2fnm'%self.wfeAl)
                if self.nGs == 1:
                    print('.Noise error:\t\t\t%4.2fnm'%self.wfeN)
                else:
                    print('.Noise error:\t\t\t%4.2fnm'%self.wfeN[idCenter])
                print('.Spatio-temporal error:\t\t%4.2fnm'%self.wfeST[idCenter])
                print('.Additionnal jitter:\t\t%4.2fmas / %4.2fnm'%(np.mean(self.ao.wfs.detector.spotFWHM[0:1]),self.wfeJitter))
                print('-------------------------------------------')
                print('.Sole servoLag error:\t\t%4.2fnm'%self.wfeS)
                print('-------------------------------------------')            
                if self.nGs == 1:
                    print('.Sole anisoplanatism error:\t%4.2fnm'%self.wfeAni[idCenter])
                else:
                    print('.Sole tomographic error:\t%4.2fnm'%self.wfeTomo[idCenter])
                print('-------------------------------------------')
                
        self.t_errorBreakDown = 1000*(time.time() - tstart)
    
    
    def pointSpreadFunction(self,x0=None,nPix=None,verbose=False,fftphasor=False):
        """
          Computation of the PSF
        """
        
        tstart  = time.time()
        
        # INSTANTIATING THE OUTPUTS
        if self.ao.error:
            print("The fourier Model class must be instantiated first\n")
            return 0,0
        
        if x0 == None:
            jitterX = self.ao.cam.spotFWHM[0][0]
            jitterY = self.ao.cam.spotFWHM[0][1]
            jitterT = self.ao.cam.spotFWHM[0][2]* np.pi/180
            F  = np.array(self.ao.cam.transmittance)[:,np.newaxis]
            dx = np.array(self.ao.cam.dispersion[0])[:,np.newaxis]
            dy = np.array(self.ao.cam.dispersion[1])[:,np.newaxis]
            bkg= 0.0
        else:
            jitterX = x0[0]
            jitterY = x0[1]
            jitterT = x0[2]* np.pi/180
            F       = x0[3:3+self.ao.src.nSrc] * np.array(self.ao.cam.transmittance)[np.newaxis,:]
            dx      = x0[3+self.ao.src.nSrc:3+2*self.ao.src.nSrc] + np.array(self.ao.cam.dispersion[0])[np.newaxis,:]
            dy      = x0[3+2*self.ao.src.nSrc:3+3*self.ao.src.nSrc] + np.array(self.ao.cam.dispersion[1])[np.newaxis,:]
            bkg     = x0[3+3*self.ao.src.nSrc]
            
        if nPix == None:
            nPix = self.freq.nOtf
         
        PSF = np.zeros((nPix,nPix,self.ao.src.nSrc,self.freq.nWvl))
        SR  = np.zeros((self.ao.src.nSrc,self.freq.nWvl))
     
        # GET THE AO RESIDUAL PHASE STRUCTURE FUNCTION    
        cov = fft.fftshift(fft.fftn(fft.fftshift(self.PSD,axes=(0,1)),axes=(0,1)),axes=(0,1))
        self.sf  = 2*np.real(cov.max(axis=(0,1)) - cov)
        
        # DEFINING THE RESIDUAL JITTER KERNEL
        if jitterX!=0 or jitterY!=0:
            # geometry
            U2 = np.cos(jitterT) * self.freq.U_ + np.sin(jitterT) * self.freq.V_
            V2 = np.cos(jitterT) * self.freq.V_ - np.sin(jitterT) * self.freq.U_
            # Gaussian kernel
            # note 1 : Umax = self.samp*self.tel.D/self.wvlRef/(3600*180*1e3/np.pi) = 1/(2*psInMas)
            # note 2 : the 1.16 factor is needed to get FWHM=jitter for jitter-limited PSF; needed to be figured out
            Umax         = self.freq.samp*self.ao.tel.D/self.freq.wvl/(3600*180*1e3/np.pi)
            ff_jitter    = 1.16
            normFact     = ff_jitter*np.max(Umax)**2 *(2 * np.sqrt(2*np.log(2)))**2 #1.16
            Djitter      = normFact * (jitterX**2 * U2**2  + jitterY**2 * V2**2)
            self.Kjitter = np.exp(-0.5 * Djitter)
        else:
            self.Kjitter = 1
            
        # DEFINE THE FFT PHASOR AND MULTIPLY TO THE TELESCOPE OTF
        if fftphasor:
            # shift by half a pixel
            self.fftPhasor = np.exp(0.5*np.pi*complex(0,1)*(dx*self.freq.U_ + dy*self.freq.V_))
        else:
            self.fftPhasor = 1

        # LOOP ON WAVELENGTHS   
        for j in range(self.freq.nWvl):
            
            # UPDATE THE INSTRUMENTAL OTF
            if self.ao.tel.opdMap_ext != None:
                self.otfNCPA, _ = FourierUtils.getStaticOTF(self.ao.tel,self.nOtf,self.samp[j],self.freq.wvl[j], apodizer=self.ao.tel.apodizer,opdMap_ext=self.ao.tel.opdMap_ext)
                self.otfDL,_  = FourierUtils.getStaticOTF(self.ao.tel,self.nOtf,self.sampRef,self.wvlRef, apodizer=self.ao.tel.apodizer)
                
            # UPDATE THE RESIDUAL JITTER
            if self.freq.shannon == True and self.freq.nWvl > 1 and (np.any(self.ao.wfs.detector.spotFWHM)):
                normFact2    = ff_jitter*(self.freq.samp[j]*self.ao.tel.D/self.freq.wvl[j]/(3600*180*1e3/np.pi))**2  * (2 * np.sqrt(2*np.log(2)))**2
                self.Kjitter = np.exp(-0.5 * Djitter * normFact2/normFact)    
                          
            # OTF MULTIPLICATION
            otfStat = self.freq.otfNCPA * self.fftPhasor * self.Kjitter    
            otfStat = np.repeat(otfStat[:,:,np.newaxis],self.ao.src.nSrc,axis=2)      
            otfTurb = np.exp(-0.5*self.sf*(2*np.pi*1e-9/self.freq.wvl[j])**2)
            otfTot  = fft.fftshift(otfTurb * otfStat,axes=(0,1))
            
            # GET THE FINAL PSF
            psf = np.real(fft.fftshift(fft.ifftn(otfTot,axes=(0,1)),axes = (0,1)))
            # managing the undersampling
            if self.freq.samp[j] <1: 
                psf = FourierUtils.interpolateSupport(psf,round(self.ao.tel.resolution*2*self.samp[j]).astype('int'))
            if nPix != self.freq.nOtf:
                psf = FourierUtils.cropSupport(psf,self.freq.nOtf/nPix)   
            PSF[:,:,:,j] = psf/psf.sum() * F[np.newaxis,np.newaxis,:,j]
                
            # STREHL-RATIO COMPUTATION
            SR[:,j] = 1e2*np.abs(otfTot).sum(axis=(0,1))/np.real(self.freq.otfDL.sum())

        self.t_getPSF = 1000*(time.time() - tstart)
        
        return PSF+bkg, SR

    def __call__(self,x0,nPix=None):
        
        psf,_ = self.pointSpreadFunction(x0=x0,nPix=nPix,verbose=False,fftphasor=True)
        return psf    
    
    def getPsfMetrics(self,getEnsquaredEnergy=False,getEncircledEnergy=False,getFWHM=False):
        tstart  = time.time()
        self.FWHM = np.zeros((2,self.ao.src.nSrc,self.freq.nWvl))
                    
        if getEnsquaredEnergy==True:
            self.EnsqE   = np.zeros((int(self.freq.nOtf/2)+1,self.ao.src.nSrc,self.freq.nWvl))
        if getEncircledEnergy==True:
            rr,radialprofile = FourierUtils.radial_profile(self.PSF[:,:,0,0])
            self.EncE   = np.zeros((len(radialprofile),self.ao.src.nSrc,self.freq.nWvl))
        for n in range(self.ao.src.nSrc):
            for j in range(self.freq.nWvl):
                if getFWHM == True:
                    self.FWHM[:,n,j]  = FourierUtils.getFWHM(self.PSF[:,:,n,j],self.freq.psInMas[j],rebin=1,method='contour',nargout=2)
                if getEnsquaredEnergy == True:
                    self.EnsqE[:,n,j] = 1e2*FourierUtils.getEnsquaredEnergy(self.PSF[:,:,n,j])
                if getEncircledEnergy == True:
                    self.EncE[:,n,j]  = 1e2*FourierUtils.getEncircledEnergy(self.PSF[:,:,n,j])
                        
        self.t_getPsfMetrics = 1000*(time.time() - tstart)
                
    def displayResults(self,eeRadiusInMas=75,displayContour=False):
        """
        """
        tstart  = time.time()
        
        if hasattr(self,'PSF'):
            if (self.PSF.ndim == 2):
                plt.figure()
                plt.imshow(np.log10(np.abs(self.PSF)))   
            
            else:
                # GEOMETRY
                plt.figure()
                plt.polar(self.ao.src.azimuth*deg2rad,self.ao.src.zenith,'ro',markersize=7,label='PSF evaluation (arcsec)')
                plt.polar(self.gs.azimuth*deg2rad,self.gs.zenith,'bs',markersize=7,label='GS position')
                plt.polar(self.ao.dms.opt_dir[1]*deg2rad,self.ao.dms.opt_dir[0],'kx',markersize=10,label='Optimization directions')
                plt.legend(bbox_to_anchor=(1.05, 1))
                   
                # PSFs
                if np.any(self.PSF):   
                    nmin = self.ao.src.zenith.argmin()
                    nmax = self.ao.src.zenith.argmax()
                    plt.figure()
                    if self.PSF.shape[2] >1 and self.PSF.shape[3] == 1:             
                        plt.title("PSFs at {:.1f} and {:.1f} arcsec from center".format(self.ao.src.zenith[nmin],self.ao.src.zenith[nmax]))
                        P = np.concatenate((self.PSF[:,:,nmin,0],self.PSF[:,:,nmax,0]),axis=1)
                    elif self.PSF.shape[2] >1 and self.PSF.shape[3] >1:
                        plt.title("PSFs at {:.0f} and {:.0f} arcsec from center\n - Top: {:.0f}nm - Bottom:{:.0f} nm".format(self.ao.src.zenith[0],self.ao.src.zenith[-1],1e9*self.wvl[0],1e9*self.wvl[-1]))
                        P1 = np.concatenate((self.PSF[:,:,nmin,0],self.PSF[:,:,nmax,0]),axis=1)
                        P2 = np.concatenate((self.PSF[:,:,nmin,-1],self.PSF[:,:,nmax,-1]),axis=1)
                        P  = np.concatenate((P1,P2),axis=0)
                    else:
                        plt.title('PSF')
                        P = self.PSF[:,:,nmin,0]
                    plt.imshow(np.log10(np.abs(P)))
            
               
                if displayContour == True and np.any(self.SR) and self.SR.size > 1:
                    self.displayPsfMetricsContours(eeRadiusInMas=eeRadiusInMas)
                else:
                    # STREHL-RATIO
                    if hasattr(self,'SR') and np.any(self.SR) and self.SR.size > 1:
                        plt.figure()
                        plt.plot(self.ao.src.zenith,self.SR[:,0],'bo',markersize=10)
                        plt.xlabel("Off-axis distance")
                        plt.ylabel("Strehl-ratio at {:.1f} nm (percents)".format(self.wvlSrc[0]*1e9))
                        plt.show()
          
                    # FWHM
                    if hasattr(self,'FWHM') and np.any(self.FWHM) and self.FWHM.size > 1:
                        plt.figure()
                        plt.plot(self.ao.src.zenith,0.5*(self.FWHM[0,:,0]+self.FWHM[1,:,0]),'bo',markersize=10)
                        plt.xlabel("Off-axis distance")
                        plt.ylabel("Mean FWHM at {:.1f} nm (mas)".format(self.freq.wvlRef*1e9))
                        plt.show()
                 
                    # Ensquared energy
                    if hasattr(self,'EnsqE') and np.any(self.EnsqE):
                        nntrue      = eeRadiusInMas/self.freq.psInMas[0]
                        nn2         = int(nntrue)
                        EEmin       = self.EnsqE[nn2,:,0]
                        EEmax       = self.EnsqE[nn2+1,:,0]
                        EEtrue      = (nntrue - nn2)*EEmax + (nn2+1-nntrue)*EEmin
                        plt.figure()
                        plt.plot(self.ao.src.zenith,EEtrue,'bo',markersize=10)
                        plt.xlabel("Off-axis distance")
                        plt.ylabel("{:.1f}-mas-side Ensquared energy at {:.1f} nm (percents)".format(eeRadiusInMas,self.freq.wvlRef*1e9))
                        plt.show()
        
                    if hasattr(self,'EncE') and np.any(self.EncE):
                        nntrue      = eeRadiusInMas/self.freq.psInMas[0]
                        nn2         = int(nntrue)
                        EEmin       = self.EncE[nn2,:,0]
                        EEmax       = self.EncE[nn2+1,:,0]
                        EEtrue      = (nntrue - nn2)*EEmax + (nn2+1-nntrue)*EEmin
                        plt.figure()
                        plt.plot(self.ao.src.zenith,EEtrue,'bo',markersize=10)
                        plt.xlabel("Off-axis distance")
                        plt.ylabel("{:.1f}-mas-diameter Encircled energy at {:.1f} nm (percents)".format(eeRadiusInMas*2,self.freq.wvlRef*1e9))
                        plt.show()
        
        self.t_displayResults = 1000*(time.time() - tstart)
            
    def displayPsfMetricsContours(self,eeRadiusInMas=75):

        tstart  = time.time()
        # Polar to cartesian
        x = self.ao.src.zenith * np.cos(np.pi/180*self.ao.src.azimuth)
        y = self.ao.src.zenith * np.sin(np.pi/180*self.ao.src.azimuth)
    

        nn          = int(np.sqrt(self.SR.shape[0]))
        if nn**2 == self.SR.shape[0]:
            nIntervals  = nn
            X           = np.reshape(x,(nn,nn))    
            Y           = np.reshape(y,(nn,nn))
        
            # Strehl-ratio
            SR = np.reshape(self.SR[:,0],(nn,nn))
            plt.figure()
            contours = plt.contour(X, Y, SR, nIntervals, colors='black')
            plt.clabel(contours, inline=True,fmt='%1.1f')
            plt.contourf(X,Y,SR)
            plt.title("Strehl-ratio at {:.1f} nm (percents)".format(self.freq.wvlRef*1e9))
            plt.colorbar()
        
            # FWHM
            if np.any(self.FWHM) and self.FWHM.size > 1:
                FWHM = np.reshape(0.5*(self.FWHM[0,:,0] + self.FWHM[1,:,0]),(nn,nn))
                plt.figure()
                contours = plt.contour(X, Y, FWHM, nIntervals, colors='black')
                plt.clabel(contours, inline=True,fmt='%1.1f')
                plt.contourf(X,Y,FWHM)
                plt.title("Mean FWHM at {:.1f} nm (mas)".format(self.wvlSrc[0]*1e9))
                plt.colorbar()
        
            # Ensquared Enery
            if np.any(self.EnsqE) and self.EnsqE.shape[1] > 1:
                nntrue      = eeRadiusInMas/self.freq.psInMas[0]
                nn2         = int(nntrue)
                EEmin       = self.EnsqE[nn2,:,0]
                EEmax       = self.EnsqE[nn2+1,:,0]
                EEtrue      = (nntrue - nn2)*EEmax + (nn2+1-nntrue)*EEmin
                EE          = np.reshape(EEtrue,(nn,nn))
                plt.figure()
                contours = plt.contour(X, Y, EE, nIntervals, colors='black')
                plt.clabel(contours, inline=True,fmt='%1.1f')
                plt.contourf(X,Y,EE)
                plt.title("{:.1f}-mas-side Ensquared energy at {:.1f} nm (percents)".format(eeRadiusInMas*2,self.wvlSrc[0]*1e9))
                plt.colorbar()
            
            # Encircled Enery
            if np.any(self.EncE) and self.EncE.shape[1] > 1:
                nntrue      = eeRadiusInMas/self.freq.psInMas[0]
                nn2         = int(nntrue)
                EEmin       = self.EncE[nn2,:,0]
                EEmax       = self.EncE[nn2+1,:,0]
                EEtrue      = (nntrue - nn2)*EEmax + (nn2+1-nntrue)*EEmin
                EE          = np.reshape(EEtrue,(nn,nn))
                plt.figure()
                contours = plt.contour(X, Y, EE, nIntervals, colors='black')
                plt.clabel(contours, inline=True,fmt='%1.1f')
                plt.contourf(X,Y,EE)
                plt.title("{:.1f}-mas-diameter Encircled energy at {:.1f} nm (percents)".format(eeRadiusInMas*2,self.wvlSrc[0]*1e9))
                plt.colorbar()
        else:
            print('You must define a square grid for PSF evaluations directions - no contours plots avalaible')
            
        self.t_displayPsfMetricsContours = 1000*(time.time() - tstart)
    
    def displayExecutionTime(self):
        
        # total
        print("Required time for total calculation (ms)\t : {:f}".format(self.t_init))
        print("Required time for AO system model init (ms)\t : {:f}".format(self.t_initAO))
        if self.ao.error == False:
            print("Required time for frequency domain init (ms)\t : {:f}".format(self.t_initFreq))
            print("Required time for reconstructors init (ms)\t : {:f}".format(self.t_reconstructor))
            print("Required time for final PSD calculation (ms)\t : {:f}".format(self.t_powerSpectrumDensity))

            # Reconstructors
            if self.ao.rtc.holoop['gain'] > 0:
                if self.nGs > 1:
                    print("Required time for optimization init (ms)\t : {:f}".format(self.t_finalReconstructor))
                    print("Required time for tomography init (ms)\t\t : {:f}".format(self.t_tomo))
                    print("Required time for optimization init (ms)\t : {:f}".format(self.t_opt))
                # Controller
                print("Required time for controller instantiation (ms)\t : {:f}".format(self.t_controller))
                # PSD
                print("Required time for fitting PSD calculation (ms)\t : {:f}".format(self.t_fittingPSD))
                print("Required time for aliasing PSD calculation (ms)\t : {:f}".format(self.t_aliasingPSD))
                print("Required time for noise PSD calculation (ms)\t : {:f}".format(self.t_noisePSD))
                print("Required time for ST PSD calculation (ms)\t : {:f}".format(self.t_spatioTemporalPSD))
                
                # Error breakdown
                if hasattr(self,'t_errorBreakDown'):
                    print("Required time for error calculation (ms)\t : {:f}".format(self.t_errorBreakDown))
                    
                # PSF metrics
                if hasattr(self,'t_getPsfMetrics'):
                    print("Required time for get PSF metrics (ms)\t\t : {:f}".format(self.t_getPsfMetrics))
                
                # Display
                if self.display and self.calcPSF:
                    print("Required time for displaying figures (ms)\t : {:f}".format(self.t_displayResults))
                    
            if self.calcPSF:
                print("Required time for all PSFs calculation (ms)\t : {:f}".format(self.t_getPSF))