package farm.kisamore.battle

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var serverButton: Button
    private var useRussianServer = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        useRussianServer = getPreferences(MODE_PRIVATE).getBoolean("use_ru_server", true)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(7, 20, 15))
        }

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(18, 10, 10, 10)
            setBackgroundColor(Color.rgb(16, 37, 28))
        }

        val title = TextView(this).apply {
            text = "KISAMORE  BATTLE"
            setTextColor(Color.rgb(93, 211, 158))
            textSize = 18f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        bar.addView(title, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

        serverButton = Button(this).apply {
            textSize = 11f
            setOnClickListener {
                useRussianServer = !useRussianServer
                getPreferences(MODE_PRIVATE).edit().putBoolean("use_ru_server", useRussianServer).apply()
                updateServerButton()
                webView.loadUrl(battleUrl())
            }
        }
        bar.addView(serverButton, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        webView = WebView(this)
        root.addView(bar, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(webView, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mediaPlaybackRequiresUserGesture = false
            userAgentString = userAgentString + " KisaMoreBattleAndroid/0.1"
        }
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()

        updateServerButton()
        webView.loadUrl(battleUrl())
    }

    private fun battleUrl(): String = if (useRussianServer) {
        "https://ru.kisamore.farm/battle"
    } else {
        "https://kisamore.farm/battle"
    }

    private fun updateServerButton() {
        serverButton.text = if (useRussianServer) "RU" else "GLOBAL"
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }
}
