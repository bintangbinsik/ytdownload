import streamlit as st
import os
import yt_dlp
from moviepy.editor import ColorClip, TextClip, CompositeVideoClip, AudioFileClip
import whisper_timestamped as whisper
import torch

def download_youtube_audio(url, output_path='audio.mp4'):
    """Mengunduh trek audio YouTube saja dengan konversi aman untuk menghindari blokir format."""
    cookie_file = 'youtube.com_cookies.txt'
    
    ydl_opts = {
        # Mengunduh audio terbaik saja (sangat jarang diblokir oleh YouTube)
        'format': 'bestaudio/best',
        'outtmpl': 'downloaded_audio_temp.%(ext)s',
        'overwrites': True,
        'cachedir': False,
        'nocheckcertificate': True,
        
        # Mengonversi paksa trek audio ke format m4a/mp3 yang kompatibel dengan MoviePy
        'postprocs': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    }
    
    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.cache.remove()
        except Exception:
            pass
        
        ydl.extract_info(url, download=True)
        # Output hasil ekstraksi audio otomatis berformat .m4a
        downloaded_file = 'downloaded_audio_temp.m4a'
        
        if os.path.exists(downloaded_file):
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(downloaded_file, output_path)
            
    return output_path

def make_shorts_with_subtitles(audio_path, start_time, end_time, output_path='shorts_final.mp4'):
    """Memotong durasi audio, mendeteksi teks AI Whisper, dan membuat video vertikal bersubtitle."""
    # 1. Potong durasi file audio asli
    full_audio = AudioFileClip(audio_path)
    cut_audio = full_audio.subclip(start_time, end_time)
    cut_audio.write_audiofile('temp_cut.wav', logger=None)
    
    # 2. Proses AI Whisper untuk ekstraksi teks subtitle dari potongan audio
    audio_data = whisper.load_audio('temp_cut.wav')
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("tiny", device=device) 
    result = whisper.transcribe(model, audio_data, language="id")

    # 3. Membuat kanvas latar belakang vertikal Shorts (Ukuran 720x1280 rasio 9:16)
    duration = end_sec - start_sec
    bg_clip = ColorClip(size=(720, 1280), color=(15, 15, 15)).set_duration(duration)
    
    text_clips = []
    # Memproses penempatan kata hasil transkripsi AI ke kanvas video
    for segment in result['segments']:
        for word_info in segment['words']:
            text = word_info['text']
            start = word_info['start']
            end = word_info['end']
            
            # Subtitle teks kuning tebal dengan garis tepi hitam di tengah layar
            txt_clip = (TextClip(text, fontsize=55, color='yellow', font='Liberation-Sans-Bold', 
                                 stroke_color='black', stroke_width=3)
                        .set_start(start)
                        .set_duration(end - start)
                        .set_position(('center', 'center')))
            text_clips.append(txt_clip)

    # 4. Menggabungkan latar belakang, semua teks subtitle, dan memasukkan trek audio potongan
    final_video = CompositeVideoClip([bg_clip] + text_clips)
    final_video = final_video.set_audio(cut_audio)
    
    # Simpan hasil akhir ke file video mp4
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    # Tutup aset memori untuk mencegah crash server
    full_audio.close()
    cut_audio.close()
    bg_clip.close()
    final_video.close()
    for tc in text_clips:
        tc.close()
        
    if os.path.exists('temp_cut.wav'): os.remove('temp_cut.wav')
    return output_path

# =====================================================================
# TAMPILAN INTERFACES STREAMLIT
# =====================================================================
st.set_page_config(page_title="AI Audio Shorts Generator", page_icon="🎙️")

st.title("🎙️ AI Audio-to-Shorts Generator")
st.write("Ekstrak audio dari video YouTube panjang dan ubah menjadi video Shorts vertikal dengan subtitle otomatis.")

url_input = st.text_input("Masukkan URL Video YouTube:")
col1, col2 = st.columns(2)
with col1:
    start_sec = st.number_input("Mulai dari detik ke-:", min_value=0, value=10)
with col2:
    end_sec = st.number_input("Selesai pada detik ke-:", min_value=1, value=25)

if st.button("🚀 Mulai Proses Pembuatan Shorts", type="primary"):
    if not url_input:
        st.error("Silakan masukkan URL YouTube terlebih dahulu!")
    elif start_sec >= end_sec:
        st.error("Detik mulai harus lebih kecil dari detik selesai!")
    elif (end_sec - start_sec) > 30:
        st.warning("Durasi video dibatasi maksimal 30 detik demi stabilitas server.")
    else:
        try:
            status = st.empty()
            
            status.info("📥 Langkah 1: Sedang mengunduh audio YouTube (Aman dari Blokir)...")
            raw_audio = download_youtube_audio(url_input)
            
            status.info("✍️ Langkah 2: AI Whisper mendeteksi suara & merangkai video subtitle...")
            final_output = make_shorts_with_subtitles(raw_audio, start_sec, end_sec)
            
            status.empty()
            st.success("🎉 Video Shorts Berhasil Dibuat!")
            st.video(final_output)
            
            with open(final_output, "rb") as file:
                st.download_button(label="💾 Download Video Shorts", data=file, file_name="shorts_audio_output.mp4", mime="video/mp4")
                
            if os.path.exists(raw_audio): os.remove(raw_audio)
            if os.path.exists(final_output): os.remove(final_output)
                
        except Exception as e:
            st.error(f"Terjadi kendala teknis saat memproses: {str(e)}")
