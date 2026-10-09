package farm.kisamore.battle

import android.graphics.Bitmap
import android.util.LruCache
import android.widget.ImageView

/**
 * Retains the last successfully decoded camera frame across screen rebuilds.
 * Never clears an ImageView while the next frame is downloading.
 */
internal object PhotoFrameCache {
    private val frames = object : LruCache<String, Bitmap>(16 * 1024) {
        override fun sizeOf(key: String, value: Bitmap): Int =
            (value.byteCount / 1024).coerceAtLeast(1)
    }

    @Synchronized fun current(url: String): Bitmap? = frames.get(url)
    @Synchronized fun remember(url: String, bitmap: Bitmap) { frames.put(url, bitmap) }

    fun showPrevious(image: ImageView, url: String) {
        current(url)?.let { image.setImageBitmap(it) }
    }
}
