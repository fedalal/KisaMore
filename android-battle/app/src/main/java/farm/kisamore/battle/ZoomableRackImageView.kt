package farm.kisamore.battle

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.widget.ImageView
import kotlin.math.min

/** Full-photo pinch zoom, focal-point preservation and bounded panning. */
internal class ZoomableRackImageView(context: Context) : ImageView(context) {
    private val transform = Matrix()
    private var bitmapWidth = 0
    private var bitmapHeight = 0
    private var zoom = 1f
    private var offsetX = 0f
    private var offsetY = 0f
    private var downX = 0f
    private var downY = 0f
    val zoomFactor: Float get() = zoom

    private val pinch = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(detector: ScaleGestureDetector): Boolean {
            changeZoom(zoom * detector.scaleFactor, detector.focusX, detector.focusY)
            return true
        }
    })
    private val gestures = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
        override fun onDown(e: MotionEvent): Boolean = true
        override fun onDoubleTap(e: MotionEvent): Boolean {
            changeZoom(if (zoom > 1.05f) 1f else 2.5f, e.x, e.y)
            return true
        }
    })

    init {
        scaleType = ScaleType.MATRIX
        isClickable = true
        contentDescription = "Photo. Pinch or double tap to zoom"
    }

    fun displayPhoto(bitmap: Bitmap) {
        bitmapWidth = bitmap.width
        bitmapHeight = bitmap.height
        zoom = 1f
        offsetX = 0f
        offsetY = 0f
        setImageBitmap(bitmap)
        renderTransform()
    }

    fun resetZoom() {
        zoom = 1f
        offsetX = 0f
        offsetY = 0f
        renderTransform()
    }
    fun zoomIn() = changeZoom(zoom * 1.6f, width / 2f, height / 2f)
    fun zoomOut() = changeZoom(zoom / 1.6f, width / 2f, height / 2f)

    private fun changeZoom(newZoom: Float, focusX: Float, focusY: Float) {
        val bounded = newZoom.coerceIn(1f, 6f)
        if (zoom != bounded) {
            val factor = bounded / zoom
            offsetX = factor * offsetX + (1f - factor) * (focusX - width / 2f)
            offsetY = factor * offsetY + (1f - factor) * (focusY - height / 2f)
            zoom = bounded
            renderTransform()
        }
    }

    private fun renderTransform() {
        if (bitmapWidth <= 0 || bitmapHeight <= 0 || width <= 0 || height <= 0) return
        val fit = min(width.toFloat() / bitmapWidth, height.toFloat() / bitmapHeight)
        val scale = fit * zoom
        val drawW = bitmapWidth * scale
        val drawH = bitmapHeight * scale
        val maxX = ((drawW - width) / 2f).coerceAtLeast(0f)
        val maxY = ((drawH - height) / 2f).coerceAtLeast(0f)
        offsetX = offsetX.coerceIn(-maxX, maxX)
        offsetY = offsetY.coerceIn(-maxY, maxY)
        transform.reset()
        transform.setScale(scale, scale)
        transform.postTranslate((width - drawW) / 2f + offsetX, (height - drawH) / 2f + offsetY)
        imageMatrix = transform
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        renderTransform()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        gestures.onTouchEvent(event)
        pinch.onTouchEvent(event)
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                downX = event.getX(0)
                downY = event.getY(0)
            }
            MotionEvent.ACTION_MOVE -> {
                if (event.pointerCount == 1 && !pinch.isInProgress && zoom > 1.001f) {
                    offsetX += event.x - downX
                    offsetY += event.y - downY
                    renderTransform()
                }
                downX = event.getX(0)
                downY = event.getY(0)
            }
            MotionEvent.ACTION_POINTER_UP -> {
                val remainingIndex = if (event.actionIndex == 0 && event.pointerCount > 1) 1 else 0
                downX = event.getX(remainingIndex)
                downY = event.getY(remainingIndex)
            }
            MotionEvent.ACTION_UP -> performClick()
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }
}
