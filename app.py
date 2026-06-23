import streamlit as st
import os
import yt_dlp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper_timestamped as whisper
import torch

# =====================================================================
# FUNCTION BACKEND: UNDUH, POTONG, & SUBTITLE VIDEO
# =====================================================================

def download_youtube_video(url, output_path='video.mp4'):
    """Mengunduh video YouTube dengan opsi optimasi agar hemat memori."""
    ydl_opts = {
        # Mengunduh kualitas menengah (maksimal 720p) agar server Streamlit tidak crash
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        'outtmpl': output_path,
        'overwrites': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return output_path

def crop_to_shorts(video_path, start_time, end_time, output_path='shorts_cropped.mp4'):
    """Memotong durasi video dan mengubah aspek rasio menjadi vertikal (9:16)."""
    clip = VideoFileClip(video_path).subclip(start_time, end_time)
    w, h = clip.size
    new_w = int(h * 9 / 16)
    
    # Memotong bagian tengah video otomatis (Center Crop)
    cropped_clip = clip.crop(x_center=w/2, width=new_w, height=h)
    cropped_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    
    # Menutup clip asli untuk mengosongkan memori RAM
    clip.close()
    cropped_clip.close()
    return output_path

def generate_subtitles(video_path, output_path='shorts_final.mp4'):
    """Mendeteksi suara dengan AI Whisper dan menempelkan subtitle per kata."""
    audio = whisper.load_audio(video_path)
    
    # Otomatis menggunakan GPU jika tersedia, jika tidak akan memakai CPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Menggunakan model 'tiny' karena sangat ringan dan aman untuk server gratis
    model = whisper.load_model("tiny", device=device) 
    result = whisper.transcribe(model, audio, language="id")

    video = VideoFileClip(video_path)
    text_clips = []

    # Memproses penempatan kata dan timestamp hasil transkripsi AI
    for segment in result['segments']:
        for word_info in segment['words']:
            text = word_info['text']
            start = word_info['start']
            end = word_info['end']
            
            # Membuat komponen teks (Subtitle bergaya kuning tebal dengan garis tepi hitam)
            txt_clip = (TextClip(text, fontsize=42, color='yellow', font='Liberation-Sans-Bold', 
                                 stroke_color='black', stroke_width=2)
                        .set_start(start)
                        .set_duration(end - start)
                        .set_position(('center', 0.75), relative=True)) # Posisi di area bawah video
            text_clips.append(txt_clip)

    # Menggabungkan video vertikal dengan semua potongan teks subtitle
    final_video = CompositeVideoClip([video] + text_clips)
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    
    # Menutup semua clip setelah selesai untuk mencegah kebocoran memori RAM
    video.close()
    final_video.close()
    for tc in text_clips:
        tc.close()
        
    return output_path

# =====================================================================
# FRONTEND INTERFACE: TAMPILAN WEBSITE STREAMLIT
# =====================================================================

st.set_page_config(page_title="Auto Shorts Generator", page_icon="🎬", layout="centered")

st.title("🎬 AI YouTube to Shorts Generator")
st.write("Ubah video YouTube panjang menjadi Shorts vertikal 9:16 lengkap dengan subtitle otomatis bahasa Indonesia.")

# Kolom Input URL dari pengguna
url_input = st.text_input("Masukkan URL Video YouTube:", placeholder="https://youtube.com...")

# Kolom Input Durasi Potong Video
col1, col2 = st.columns(2)
with col1:
    start_sec = st.number_input("Mulai dari detik ke-:", min_value=0, value=10, step=1)
with col2:
    end_sec = st.number_input("Selesai pada detik ke-:", min_value=1, value=25, step=1)

# Tombol untuk mengeksekusi program
if st.button("🚀 Mulai Proses Video", type="primary"):
    if not url_input:
        st.error("Silakan masukkan tautan URL YouTube terlebih dahulu!")
    elif start_sec >= end_sec:
        st.error("Detik mulai harus lebih kecil dari detik selesai video!")
    elif (end_sec - start_sec) > 30:
        st.warning("Demi stabilitas server gratis, durasi video dibatasi maksimal 30 detik.")
    else:
        try:
            # Container status pengingat proses
            status = st.empty()
            
            status.info("📥 Langkah 1: Sedang mengunduh video dari YouTube...")
            raw_video = download_youtube_video(url_input)
            
            status.info("✂️ Langkah 2: Memotong video menjadi format vertikal (9:16)...")
            cropped_video = crop_to_shorts(raw_video, start_sec, end_sec)
            
            status.info("✍️ Langkah 3: AI Whisper sedang memproses teks & menempelkan subtitle...")
            final_output = generate_subtitles(cropped_video)
            
            # Bersihkan status info setelah berhasil
            status.empty()
            st.success("🎉 Video Shorts Berhasil Dibuat!")
            
            # Menampilkan pratinjau video hasil akhir langsung di browser
            st.video(final_output)
            
            # Menyediakan tombol download instan untuk pengguna
            with open(final_output, "rb") as file:
                st.download_button(
                    label="💾 Download Video Shorts",
                    data=file,
                    file_name="shorts_output.mp4",
                    mime="video/mp4"
                )
                
            # Membersihkan file sampah temporary di server setelah berhasil didownload
            if os.path.exists(raw_video): os.remove(raw_video)
            if os.path.exists(cropped_video): os.remove(cropped_video)
            if os.path.exists(final_output): os.remove(final_output)
                
        except Exception as e:
            st.error(f"Terjadi kendala teknis saat memproses video: {str(e)}")
