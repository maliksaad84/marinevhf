from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import analog
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import osmosdr
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import time
import os

class DynamicMultiChannelScanner(gr.top_block, Qt.QWidget):
    def __init__(self, channel_list):
        gr.top_block.__init__(self, "Dynamic Multi-Channel Scanner", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Dynamic Multi-Channel Scanner")
        qtgui.util.check_set_qss()

        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "DynamicMultiChannelScanner")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except Exception as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        self.channel_list = channel_list
        self.samp_rate = 2500000
        self.center_freq = sum(freq for _, freq in channel_list) / len(channel_list)

        self.osmosdr_source_0 = osmosdr.source("numchan=1 airspy=0")
        self.osmosdr_source_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.osmosdr_source_0.set_sample_rate(self.samp_rate)
        self.osmosdr_source_0.set_center_freq(self.center_freq, 0)
        self.osmosdr_source_0.set_freq_corr(0, 0)
        self.osmosdr_source_0.set_dc_offset_mode(0, 0)
        self.osmosdr_source_0.set_iq_balance_mode(0, 0)
        self.osmosdr_source_0.set_gain_mode(False, 0)
        self.osmosdr_source_0.set_gain(20, 0)
        self.osmosdr_source_0.set_if_gain(15, 0)
        self.osmosdr_source_0.set_bb_gain(0, 0)
        self.osmosdr_source_0.set_antenna('', 0)
        self.osmosdr_source_0.set_bandwidth(0, 0)

        self.blocks = []

        for name, freq in self.channel_list:
            offset = self.center_freq - freq

            mixer = analog.sig_source_c(self.samp_rate, analog.GR_COS_WAVE, offset, 1, 0)
            multiply = blocks.multiply_vcc(1)
            lpf = filter.fir_filter_ccf(
                10,
                firdes.low_pass(1, self.samp_rate, 7500, 2500, window.WIN_HAMMING)
            )
            resampler = filter.rational_resampler_ccc(
                interpolation=48,
                decimation=25,
                taps=[]
            )
            squelch = analog.pwr_squelch_cc(-44, 1e-4, 0, True)
            nbfm = analog.nbfm_rx(
                audio_rate=48000,
                quad_rate=480000,
                tau=75e-6,
                max_dev=5e3
            )
            scale = blocks.multiply_const_ff(0.5)

            #out_dir = f"/home/pc0801/vhflive-station/Audio/{name}"
            #os.makedirs(out_dir, exist_ok=True)
            #outfile = os.path.join(out_dir, f"output.wav")
            outfile = f"/home/pc0801/vhflive-station/Audio/{name}.wav"
            sink = blocks.wavfile_sink(outfile, 1, 48000, blocks.FORMAT_WAV, blocks.FORMAT_PCM_16, False)

            self.connect(self.osmosdr_source_0, (multiply, 0))
            self.connect(mixer, (multiply, 1))
            self.connect(multiply, lpf)
            self.connect(lpf, resampler)
            self.connect(resampler, squelch)
            self.connect(squelch, nbfm)
            self.connect(nbfm, scale)
            self.connect(scale, sink)

            self.blocks.append({
                'name': name,
                'mixer': mixer,
                'sink': sink
            })

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()
        event.accept()

def main():
    channel_list = [
        ('C10', 156.5e6),
        ('C12', 156.6e6),
    ]

    qapp = Qt.QApplication(sys.argv)
    tb = DynamicMultiChannelScanner(channel_list)
    tb.start()
    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
