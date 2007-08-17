#!/usr/bin/env python
#
# Copyright 2007 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import math
from numpy import fft
from gnuradio import gr

class ofdm_sync_pn(gr.hier_block):
    def __init__(self, fg, fft_length, cp_length, logging=False):
        ''' OFDM synchronization using PN Correlation:
        T. M. Schmidl and D. C. Cox, "Robust Frequency and Timing
        Synchonization for OFDM," IEEE Trans. Communications, vol. 45,
        no. 12, 1997.
        '''
        
        self.fg = fg

        # FIXME: when converting to hier_block2's, the output signature
        # should be the output of the divider (the normalized peaks) and
        # the angle value out of the sample and hold block
            
        self.input = gr.add_const_cc(0)

        symbol_length = fft_length + cp_length

        # PN Sync

        # Create a delay line
        self.delay = gr.delay(gr.sizeof_gr_complex, fft_length/2)

        # Correlation from ML Sync
        self.conjg = gr.conjugate_cc();
        self.corr = gr.multiply_cc();

        # Create a moving sum filter for the corr output
        if 1:
            moving_sum_taps = [1.0 for i in range(fft_length//2)]
            self.moving_sum_filter = gr.fir_filter_ccf(1,moving_sum_taps)
        else:
            moving_sum_taps = [complex(1.0,0.0) for i in range(fft_length//2)]
            self.moving_sum_filter = gr.fft_filter_ccc(1,moving_sum_taps)

        # Create a moving sum filter for the input
        self.inputmag2 = gr.complex_to_mag_squared()
        movingsum2_taps = [1.0 for i in range(fft_length//2)]

        if 1:
            self.inputmovingsum = gr.fir_filter_fff(1,movingsum2_taps)
        else:
            self.inputmovingsum = gr.fft_filter_fff(1,movingsum2_taps)

        self.square = gr.multiply_ff()
        self.normalize = gr.divide_ff()
     
        # Get magnitude (peaks) and angle (phase/freq error)
        self.c2mag = gr.complex_to_mag_squared()
        self.angle = gr.complex_to_arg()

        self.sample_and_hold = gr.sample_and_hold_ff()

        # Mix the signal with an NCO controlled by the sync loop
        nco_sensitivity = -2.0/fft_length
        self.nco = gr.frequency_modulator_fc(nco_sensitivity)
        self.sigmix = gr.multiply_cc()

        #ML measurements input to sampler block and detect
        self.sub1 = gr.add_const_ff(-1)
        self.pk_detect = gr.peak_detector_fb(0.2, 0.25, 30, 0.0005)
        self.regen = gr.regenerate_bb(symbol_length)

        self.sampler = gr.ofdm_sampler(fft_length,symbol_length)
        
        self.fg.connect(self.input, self.delay)
        self.fg.connect(self.input, (self.corr,0))
        self.fg.connect(self.delay, self.conjg)
        self.fg.connect(self.conjg, (self.corr,1))
        self.fg.connect(self.corr, self.moving_sum_filter)
        self.fg.connect(self.moving_sum_filter, self.c2mag)
        self.fg.connect(self.moving_sum_filter, self.angle)
        self.fg.connect(self.angle, (self.sample_and_hold,0))
        self.fg.connect(self.sample_and_hold, self.nco)

        self.fg.connect(self.input, (self.sigmix,0))
        self.fg.connect(self.nco, (self.sigmix,1))
        self.fg.connect(self.sigmix, (self.sampler,0))

        self.fg.connect(self.input, self.inputmag2, self.inputmovingsum)
        self.fg.connect(self.inputmovingsum, (self.square,0))
        self.fg.connect(self.inputmovingsum, (self.square,1))
        self.fg.connect(self.square, (self.normalize,1))
        self.fg.connect(self.c2mag, (self.normalize,0))

        # Create a moving sum filter for the corr output
        matched_filter_taps = [1.0/cp_length for i in range(cp_length)]
        self.matched_filter = gr.fir_filter_fff(1,matched_filter_taps)
        self.fg.connect(self.normalize, self.matched_filter)
        
        self.fg.connect(self.matched_filter, self.sub1, self.pk_detect)
        self.fg.connect(self.pk_detect, self.regen)
        self.fg.connect(self.regen, (self.sampler,1))
        self.fg.connect(self.pk_detect, (self.sample_and_hold,1))


        if logging:
            self.fg.connect(self.matched_filter, gr.file_sink(gr.sizeof_float, "ofdm_sync_pn-mf_f.dat"))
            self.fg.connect(self.normalize, gr.file_sink(gr.sizeof_float, "ofdm_sync_pn-theta_f.dat"))
            self.fg.connect(self.angle, gr.file_sink(gr.sizeof_float, "ofdm_sync_pn-epsilon_f.dat"))
            self.fg.connect(self.pk_detect, gr.file_sink(gr.sizeof_char, "ofdm_sync_pn-peaks_b.dat"))
            self.fg.connect(self.regen, gr.file_sink(gr.sizeof_char, "ofdm_sync_pn-regen_b.dat"))
            self.fg.connect(self.sigmix, gr.file_sink(gr.sizeof_gr_complex, "ofdm_sync_pn-sigmix_c.dat"))
            self.fg.connect(self.sampler, gr.file_sink(gr.sizeof_gr_complex*fft_length, "ofdm_sync_pn-sampler_c.dat"))
            self.fg.connect(self.sample_and_hold, gr.file_sink(gr.sizeof_float, "ofdm_sync_pn-sample_and_hold_f.dat"))
            self.fg.connect(self.nco, gr.file_sink(gr.sizeof_gr_complex, "ofdm_sync_pn-nco_c.dat"))
            self.fg.connect(self.input, gr.file_sink(gr.sizeof_gr_complex, "ofdm_sync_pn-input_c.dat"))

        gr.hier_block.__init__(self, fg, self.input, self.sampler)