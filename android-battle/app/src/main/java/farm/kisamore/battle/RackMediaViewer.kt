package farm.kisamore.battle

import android.app.Activity
import android.app.Dialog
import android.content.ClipData
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import android.widget.VideoView
import java.io.File
import java.util.UUID
import kotlin.math.roundToInt

/**
 * Full-screen camera viewer for pinch zoom, drag, sharing a JPEG and
 * playing timelapses belonging to the same selected camera.
 */
internal class RackMediaViewer(
    private val host: Activity,
    private val api: ApiClient,
    private val photoUrl: String,
    private val camera: BattleCamera?
) {
    private val lang = AppLanguage(host)
    private val scale = host.resources.displayMetrics.density
    private fun dp(px: Int): Int = (px * scale + .5f).toInt()
    private fun tr(ru: String, en: String) = when (lang.code) {
        "ru" -> ru
        "en" -> en
        else -> lang.t(ru).takeUnless { it == ru } ?: en
    }
    private fun rounded(color: Int, radius: Int): GradientDrawable =
        GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat() }

    private fun label(message: String, size: Float = 14f, bold: Boolean = false): TextView =
        TextView(host).apply {
            text = message
            textSize = size
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            includeFontPadding = false
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    private fun button(message: String, action: () -> Unit): TextView =
        label(message, 14f, true).apply {
            minHeight = dp(44)
            setPadding(dp(8), dp(7), dp(8), dp(7))
            background = rounded(Color.parseColor("#23402F"), 12)
            isClickable = true
            isFocusable = true
            setOnClickListener { action() }
        }

    fun show() {
        val dialog = Dialog(host, android.R.style.Theme_Black_NoTitleBar_Fullscreen)
        // Reserve a dedicated, central media area between the header and actions.
        // Previously VideoView filled the whole Dialog, so its playback surface
        // could sit under the top toolbar instead of being centred like the photo.
        val root = LinearLayout(host).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.BLACK)
        }
        val mediaArea = FrameLayout(host)
        val photo = ZoomableRackImageView(host).apply {
            contentDescription = tr(
                "Фото полки. Для увеличения разведите пальцы или коснитесь дважды.",
                "Rack photo. Pinch or double tap to zoom."
            )
        }
        mediaArea.addView(photo, FrameLayout.LayoutParams(-1, -1))
        val video = VideoView(host).apply { visibility = View.GONE }
        mediaArea.addView(video, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
        var videoWidth = 0
        var videoHeight = 0
        fun sizeVideoToFit() {
            if (videoWidth <= 0 || videoHeight <= 0) return
            if (mediaArea.width <= 0 || mediaArea.height <= 0) return
            val (width, height) = fitRackVideo(
                videoWidth, videoHeight, mediaArea.width, mediaArea.height
            )
            val params = video.layoutParams as FrameLayout.LayoutParams
            if (params.width == width && params.height == height) return
            video.layoutParams = FrameLayout.LayoutParams(width, height, Gravity.CENTER)
        }
        mediaArea.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            sizeVideoToFit()
        }
        val loading = ProgressBar(host).apply { visibility = View.GONE }
        mediaArea.addView(loading, FrameLayout.LayoutParams(dp(32), dp(32), Gravity.CENTER))

        val header = LinearLayout(host).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rounded(Color.parseColor("#E0102218"), 0)
        }
        val headerTitle = label(tr("Фото полки", "Rack photo"), 17f, true).apply {
            gravity = Gravity.START or Gravity.CENTER_VERTICAL
        }
        header.addView(headerTitle, LinearLayout.LayoutParams(0, dp(46), 1f))

        var currentPhoto: Bitmap? = PhotoFrameCache.current(photoUrl)
        var isVideo = false

        val foot = LinearLayout(host).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(26))
            background = rounded(Color.parseColor("#E0102218"), 0)
        }
        val hint = label(
            tr("Двумя пальцами — масштаб · двойное касание", "Pinch to zoom · double tap to reset"),
            11f
        ).apply { setTextColor(Color.parseColor("#A9C7B4")) }
        foot.addView(hint, LinearLayout.LayoutParams(-1, dp(26)))

        val zoomControls = LinearLayout(host).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        fun addZoomControl(text: String, weight: Float, action: () -> Unit) {
            zoomControls.addView(button(text, action),
                LinearLayout.LayoutParams(0, dp(46), weight).apply {
                    leftMargin = dp(3); rightMargin = dp(3)
                })
        }
        addZoomControl("−", 1f) { photo.zoomOut() }
        addZoomControl(tr("По размеру", "Fit"), 2f) { photo.resetZoom() }
        addZoomControl("+", 1f) { photo.zoomIn() }
        foot.addView(zoomControls, LinearLayout.LayoutParams(-1, dp(48)))

        val clipControls = LinearLayout(host).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        var photoControl: TextView? = null
        fun restorePhoto() {
            if (isVideo) video.stopPlayback()
            isVideo = false
            video.visibility = View.GONE
            photo.visibility = View.VISIBLE
            zoomControls.visibility = View.VISIBLE
            loading.visibility = View.GONE
            headerTitle.text = tr("Фото полки", "Rack photo")
            photoControl?.alpha = 1f
        }
        fun playClip(path: String?) {
            val clipUrl = api.absolute(path)
            if (clipUrl.isNullOrBlank()) {
                Toast.makeText(host, tr("Таймлапс пока не готов", "Timelapse not ready"),
                    Toast.LENGTH_SHORT).show()
                return
            }
            isVideo = true
            photo.visibility = View.GONE
            video.visibility = View.VISIBLE
            zoomControls.visibility = View.GONE
            loading.visibility = View.VISIBLE
            headerTitle.text = tr("Таймлапс", "Timelapse")
            photoControl?.alpha = .7f
            video.setOnPreparedListener { player ->
                videoWidth = player.videoWidth
                videoHeight = player.videoHeight
                player.setOnVideoSizeChangedListener { _, width, height ->
                    videoWidth = width
                    videoHeight = height
                    mediaArea.post { sizeVideoToFit() }
                }
                // The media area has already been laid out when the async player
                // prepares. Fit before starting so the first visible frame is centred.
                sizeVideoToFit()
                loading.visibility = View.GONE
                video.start()
            }
            video.setOnCompletionListener { restorePhoto() }
            video.setOnErrorListener { _, _, _ ->
                restorePhoto()
                Toast.makeText(host,
                    tr("Не удалось воспроизвести таймлапс", "Could not play timelapse"),
                    Toast.LENGTH_SHORT).show()
                true
            }
            video.setVideoURI(Uri.parse(clipUrl))
            video.requestFocus()
        }
        val clips = listOf(
            tr("24 ч", "24 h") to camera?.timelapse24hUrl,
            tr("3 дня", "3 days") to camera?.timelapse3dUrl,
            tr("Всё", "All") to camera?.timelapseFullUrl
        )
        if (clips.any { !it.second.isNullOrBlank() }) {
            val returnToPhoto = button(tr("Фото", "Photo")) { restorePhoto() }
            photoControl = returnToPhoto
            clipControls.addView(returnToPhoto,
                LinearLayout.LayoutParams(0, dp(46), 1f).apply { rightMargin = dp(4) })
            for ((text, path) in clips) {
                val b = button("▶ " + text) { playClip(path) }
                b.isEnabled = !path.isNullOrBlank()
                b.alpha = if (b.isEnabled) 1f else .4f
                clipControls.addView(b,
                    LinearLayout.LayoutParams(0, dp(46), 1f).apply {
                        leftMargin = dp(3); rightMargin = dp(3)
                    })
            }
            foot.addView(clipControls,
                LinearLayout.LayoutParams(-1, dp(46)).apply { topMargin = dp(8) })
        }
        lateinit var shareButton: TextView
        shareButton = button(tr("↗ Поделиться", "↗ Share")) {
            val bitmap = currentPhoto
            if (bitmap == null) {
                Toast.makeText(host, tr("Фотография загружается", "Photo is loading"),
                    Toast.LENGTH_SHORT).show()
            } else {
                shareButton.isEnabled = false
                shareButton.alpha = .45f
                Thread {
                    val outcome = runCatching {
                        val folder = File(host.cacheDir, "shared_photos").apply { mkdirs() }
                        val filename = "rack_" + UUID.randomUUID().toString().replace("-", "") + ".jpg"
                        val file = File(folder, filename)
                        file.outputStream().use { output ->
                            check(bitmap.compress(Bitmap.CompressFormat.JPEG, 94, output))
                        }
                        Uri.Builder().scheme("content")
                            .authority(host.packageName + ".photos")
                            .appendPath("shared").appendPath(file.name).build()
                    }
                    host.runOnUiThread {
                        if (host.isFinishing || host.isDestroyed || !dialog.isShowing) return@runOnUiThread
                        shareButton.isEnabled = true
                        shareButton.alpha = 1f
                        outcome.onSuccess { imageUri ->
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "image/jpeg"
                                putExtra(Intent.EXTRA_STREAM, imageUri)
                                clipData = ClipData.newUri(host.contentResolver, "Rack photo", imageUri)
                                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            }
                            host.startActivity(
                                Intent.createChooser(intent, tr("Отправить фото", "Share photo"))
                                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            )
                        }.onFailure {
                            Toast.makeText(host,
                                tr("Не удалось поделиться фотографией", "Could not share photo"),
                                Toast.LENGTH_SHORT).show()
                        }
                    }
                }.start()
            }
        }
        header.addView(shareButton)
        header.addView(button("✕") { dialog.dismiss() },
            LinearLayout.LayoutParams(dp(49), dp(45)).apply { leftMargin = dp(7) })
        // Both the zoomable photo and the fitted video use this same centred
        // viewport. Neither can be drawn behind the toolbar or clip buttons.
        root.addView(header, LinearLayout.LayoutParams(-1, dp(64)))
        root.addView(mediaArea, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(foot, LinearLayout.LayoutParams(-1, -2))

        dialog.setOnDismissListener { video.stopPlayback() }
        dialog.setContentView(root)
        dialog.show()
        dialog.window?.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)

        currentPhoto?.let { photo.displayPhoto(it) }
        if (currentPhoto == null) loading.visibility = View.VISIBLE
        Thread {
            val full = api.loadBitmap(photoUrl)
            if (full != null) PhotoFrameCache.remember(photoUrl, full)
            host.runOnUiThread {
                if (!dialog.isShowing || host.isFinishing || host.isDestroyed) return@runOnUiThread
                if (full != null) {
                    currentPhoto = full
                    if (photo.zoomFactor <= 1.001f) photo.displayPhoto(full)
                    if (!isVideo) loading.visibility = View.GONE
                } else if (currentPhoto == null) {
                    loading.visibility = View.GONE
                    Toast.makeText(host, tr("Не удалось загрузить фотографию", "Could not load photo"),
                        Toast.LENGTH_SHORT).show()
                }
            }
        }.start()
    }
}


/** Aspect-preserving fit within the fullscreen viewer (never crop the movie). */
internal fun fitRackVideo(
    videoWidth: Int, videoHeight: Int, areaWidth: Int, areaHeight: Int
): Pair<Int, Int> {
    if (videoWidth <= 0 || videoHeight <= 0 || areaWidth <= 0 || areaHeight <= 0) {
        return 1 to 1
    }
    val factor = minOf(
        areaWidth.toDouble() / videoWidth,
        areaHeight.toDouble() / videoHeight
    )
    return (videoWidth * factor).roundToInt().coerceIn(1, areaWidth) to
        (videoHeight * factor).roundToInt().coerceIn(1, areaHeight)
}
