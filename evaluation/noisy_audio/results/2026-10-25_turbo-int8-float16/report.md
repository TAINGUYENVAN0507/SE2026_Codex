# Bộ ồn synthetic: `turbo-int8-float16`

- ASR: `faster-whisper:large-v3-turbo:int8_float16` trên NVIDIA GeForce GTX 1650 Ti, 4096 MiB, 580.178.04
- 10 clip FLEURS × 16 điều kiện, seed 2026
- WER cấp corpus của mọi clip trong từng điều kiện. `no_speech`: số file VAD từ chối
  (pipeline sẽ báo `NO_SPEECH_DETECTED`), chấm như hypothesis rỗng.

| Điều kiện | SNR mục tiêu | SNR đo | WER | CER | Δ WER so với clean | no_speech |
|---|---|---|---|---|---|---|
| `clean` |  |  | 0.033 | 0.018 | +0.000 | 0 |
| `pink_snr20` | 20 | 19.99 | 0.054 | 0.030 | +0.021 | 0 |
| `pink_snr10` | 10 | 10.0 | 0.078 | 0.050 | +0.045 | 0 |
| `pink_snr5` | 5 | 5.0 | 0.105 | 0.059 | +0.072 | 0 |
| `pink_snr0` | 0 | -0.03 | 0.222 | 0.136 | +0.189 | 0 |
| `white_snr20` | 20 | 19.99 | 0.063 | 0.037 | +0.030 | 0 |
| `white_snr10` | 10 | 10.0 | 0.090 | 0.052 | +0.057 | 0 |
| `white_snr5` | 5 | 5.0 | 0.141 | 0.089 | +0.108 | 0 |
| `white_snr0` | 0 | -0.01 | 0.345 | 0.272 | +0.312 | 0 |
| `brown_snr10` | 10 | 10.0 | 0.045 | 0.024 | +0.012 | 0 |
| `babble4_snr10` | 10 | 9.98 | 0.054 | 0.029 | +0.021 | 0 |
| `babble4_snr5` | 5 | 4.97 | 0.204 | 0.163 | +0.171 | 0 |
| `reverb_rt60_0.4` |  |  | 0.054 | 0.027 | +0.021 | 0 |
| `reverb_rt60_0.8` |  |  | 0.108 | 0.071 | +0.075 | 0 |
| `far_mic` |  |  | 0.195 | 0.144 | +0.162 | 0 |
| `opus_16kbps` |  |  | 0.057 | 0.032 | +0.024 | 0 |
