const express = require('express');
const { YoutubeTranscript } = require('youtube-transcript');
const ffmpeg = require('fluent-ffmpeg');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static('public'));

// Fungsi untuk mengekstrak ID Video dari URL YouTube
function extractVideoId(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

// API untuk memproses teks YouTube dan membuat video
app.post('/api/generate', async (req, res) => {
    const { url, startSec, endSec } = req.body;
    const videoId = extractVideoId(url);

    if (!videoId) {
        return res.status(400).json({ error: 'URL YouTube tidak valid!' });
    }

    try {
        // 1. Ambil subtitle resmi langsung via API (Anti Blokir)
        const transcript = await YoutubeTranscript.fetchTranscript(videoId);
        
        // Filter teks berdasarkan durasi detik yang dipilih pengguna
        const filteredText = transcript
            .filter(item => (item.offset / 1000) >= startSec && (item.offset / 1000) <= endSec)
            .map(item => item.text)
            .join(' ')
            .replace(/&amp;#39;/g, "'") // Pembersihan karakter aneh
            .replace(/\[.*?\]/g, ''); // Hapus teks petunjuk seperti [Musik]

        if (!filteredText) {
            return res.status(400).json({ error: 'Tidak ada teks ditemukan pada durasi tersebut.' });
        }

        const duration = endSec - startSec;
        const outputFilename = `shorts_${Date.now()}.mp4`;
        const outputPath = path.join(__dirname, 'public', outputFilename);

        // 2. Pembuatan Video Vertikal (9:16) menggunakan FFmpeg murni
        // Membuat kanvas hitam otomatis dan menempelkan teks kuning besar di tengah layar
        ffmpeg()
            .input('color=c=black:s=720x1280')
            .inputFormat('lavfi')
            .setDuration(duration)
            .videoFilters([
                {
                    filter: 'drawtext',
                    options: {
                        text: filteredText,
                        fontcolor: 'yellow',
                        fontsize: 36,
                        x: '(w-text_w)/2',
                        y: '(h-text_h)/2',
                        box: 1,
                        boxcolor: 'black@0.6',
                        boxborderw: 10
                    }
                }
            ])
            .outputOptions([
                '-c:v libx264',
                '-pix_fmt yuv420p',
                '-r 24'
            ])
            .save(outputPath)
            .on('end', () => {
                // Mengirimkan link download video ke halaman web jika sudah selesai
                res.json({ success: true, videoUrl: `/${outputFilename}`, text: filteredText });
            })
            .on('error', (err) => {
                console.error(err);
                res.status(500).json({ error: 'Gagal merangkai video FFmpeg.' });
            });

    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Gagal mengambil subtitle dari YouTube.' });
    }
});

app.listen(PORT, () => {
    console.log(`Server berjalan online di http://localhost:${PORT}`);
});
