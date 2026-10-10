package farm.kisamore.battle

import android.app.Activity
import android.graphics.Color
import android.net.Uri
import android.view.View
import android.widget.ImageView
import android.widget.TextView
import android.widget.VideoView
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.ConcurrentHashMap

/**
 * A bounded, disk-backed playlist for the guest screen.
 *
 * - Keep the latest greenhouse photo on screen while the first MP4 downloads.
 * - Play cached MP4s automatically, muted, in order.
 * - Download the next video *while* the current video plays.
 * - Skip unavailable/broken clips without showing a static photo in place of a video.
 * - Keep playback smooth if downloading takes longer than the current clip by replaying it.
 * - Cancel safely when the visitor changes tab.
 */
internal class GuestTimelapseQueue(
    private val activity: Activity,
    private val api: ApiClient,
    private val choices: List<HomeClip>,
    private val video: VideoView,
    private val poster: ImageView,
    private val play: TextView
) {
    private data class Ready(val path: String, val file: File)

    private val loader = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "KisaMore-home-timelapses").apply { isDaemon = true }
    }
    private val failed = ConcurrentHashMap.newKeySet<String>()
    private val cacheDir = File(activity.cacheDir, "guest-timelapses")
    @Volatile private var closed = false
    @Volatile private var playingPath: String? = null
    private var nextIndex = 0
    private var loading = false
    private var current: Ready? = null
    private var queued: Ready? = null
    private var pausedByUser = false

    fun start() {
        if (closed || choices.isEmpty()) return
        if (failed.size >= choices.size) {
            failed.clear() // A later manual retry may find newly generated timelapses.
            nextIndex = 0
        }
        // The initial photo remains visible until a real, playable video is prepared.
        fetch { ready ->
            if (ready != null) playReady(ready)
            else play.visibility = View.VISIBLE
        }
    }

    fun onPlayPressed() {
        if (closed) return
        val active = current
        if (active == null) {
            if (!loading) start()
            return
        }
        if (video.isPlaying) {
            pausedByUser = true
            video.pause()
            play.visibility = View.VISIBLE
        } else {
            pausedByUser = false
            video.start()
            play.visibility = View.GONE
        }
    }

    fun onVideoPressed() = onPlayPressed()

    private fun playReady(ready: Ready) {
        if (closed) return
        current = ready
        playingPath = ready.file.absolutePath
        video.visibility = View.VISIBLE
        video.setVideoURI(Uri.fromFile(ready.file))
        video.requestFocus()
    }

    private fun fetch(result: (Ready?) -> Unit) {
        if (closed || loading || choices.isEmpty()) return
        loading = true
        loader.execute {
            // Seek the next real timelapse, not a rack photo or a non-existent MP4.
            // After one pass, loop through successful entries again.
            var found: Ready? = null
            var attempts = 0
            while (!closed && attempts < choices.size) {
                if (nextIndex >= choices.size) nextIndex = 0
                val clip = choices[nextIndex++]
                attempts++
                if (clip.path in failed) continue
                val url = api.absolute(clip.path) ?: continue
                val file = download(url)
                if (file != null) {
                    found = Ready(clip.path, file)
                    break
                }
                failed.add(clip.path)
            }
            if (!closed) activity.runOnUiThread {
                if (!closed) {
                    loading = false
                    result(found)
                }
            }
        }
    }

    private fun prefetch() {
        if (closed || queued != null || loading) return
        fetch { ready ->
            queued = ready
            // Stay on the current video until its natural end, even if
            // the next MP4 is already in cache.
        }
    }

    init {
        video.setOnPreparedListener { player ->
            if (closed) return@setOnPreparedListener
            player.setVolume(0f, 0f)
            player.isLooping = false
            poster.visibility = View.GONE
            if (!pausedByUser) {
                play.visibility = View.GONE
                video.start()
            } else {
                play.visibility = View.VISIBLE
            }
            prefetch()
        }
        video.setOnCompletionListener {
            if (closed) return@setOnCompletionListener
            val upcoming = queued
            if (upcoming != null && upcoming.path != current?.path) {
                queued = null
                playReady(upcoming)
            } else {
                // Replaying avoids a blank frame if the prefetch is not done yet
                // or if there is only one available timelapse.
                if (upcoming != null) queued = null
                video.seekTo(0)
                video.start()
                prefetch()
            }
        }
        video.setOnErrorListener { _, _, _ ->
            if (!closed) {
                current?.file?.delete()
                current?.path?.let { failed.add(it) }
                current = null
                playingPath = null
                val upcoming = queued
                queued = null
                if (upcoming != null) {
                    video.post { if (!closed) playReady(upcoming) }
                } else {
                    poster.visibility = View.VISIBLE
                    play.visibility = View.VISIBLE
                    video.post { if (!closed) fetch { ready -> if (ready != null) playReady(ready) } }
                }
            }
            true
        }
    }

    private fun download(address: String): File? {
        if (closed) return null
        try {
            if (!cacheDir.exists() && !cacheDir.mkdirs()) return null
            val digest = MessageDigest.getInstance("SHA-256").digest(address.toByteArray())
                .joinToString("") { "%02x".format(it) }
            val saved = File(cacheDir, "$digest.mp4")
            if (saved.isFile && saved.length() in 1..MAX_VIDEO_BYTES) {
                saved.setLastModified(System.currentTimeMillis())
                return saved
            }
            val partial = File(cacheDir, "$digest.part")
            var connection: HttpURLConnection? = null
            try {
                connection = URL(address).openConnection() as HttpURLConnection
                connection.connectTimeout = 8_000
                connection.readTimeout = 30_000
                connection.setRequestProperty("Accept", "video/mp4")
                val code = connection.responseCode
                val length = connection.contentLengthLong
                val type = connection.contentType?.lowercase() ?: ""
                if (code !in 200..299 || length > MAX_VIDEO_BYTES ||
                    !(type.startsWith("video/") || type.startsWith("application/octet-stream"))
                ) return null
                var written = 0L
                connection.inputStream.use { input ->
                    FileOutputStream(partial).use { output ->
                        val buffer = ByteArray(32 * 1024)
                        while (!closed) {
                            val count = input.read(buffer)
                            if (count == -1) break
                            written += count
                            if (written > MAX_VIDEO_BYTES) return null
                            output.write(buffer, 0, count)
                        }
                    }
                }
                if (closed || written < 1000L) return null
                if (!partial.renameTo(saved)) return null
                pruneCache(saved)
                return saved
            } finally {
                connection?.disconnect()
                if (partial.exists()) partial.delete()
            }
        } catch (_: Exception) {
            return null
        }
    }

    private fun pruneCache(keep: File) {
        val files = cacheDir.listFiles { f -> f.isFile && f.name.endsWith(".mp4") }
            ?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (file in files) {
            if (total <= MAX_CACHE_BYTES) break
            if (file == keep || file.absolutePath == playingPath) continue
            val oldLength = file.length()
            if (file.delete()) total -= oldLength
        }
    }

    fun release() {
        closed = true
        loader.shutdownNow()
        video.stopPlayback()
        current = null
        queued = null
    }

    companion object {
        private const val MAX_VIDEO_BYTES = 64L * 1024 * 1024
        private const val MAX_CACHE_BYTES = 128L * 1024 * 1024
    }
}
