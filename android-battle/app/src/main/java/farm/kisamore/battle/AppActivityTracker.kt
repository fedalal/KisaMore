package farm.kisamore.battle

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Best-effort, minimal telemetry to our own API.
 * It never blocks the UI, includes no email/name/password or stack trace,
 * and works for signed-in users and guests.
 */
class AppActivityTracker(context: Context, private val api: ApiClient) {
    private val prefs = context.getSharedPreferences("kisamore_app_activity", Context.MODE_PRIVATE)
    private val installationId: String = prefs.getString("installation_id", null) ?: UUID.randomUUID().toString().also {
        prefs.edit().putString("installation_id", it).apply()
    }
    private val appVersion: String = try {
        @Suppress("DEPRECATION")
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0.6.30"
    } catch (_: Exception) {
        "0.6.30"
    }
    private val androidVersion: String = Build.VERSION.RELEASE
        .replace(Regex("[^A-Za-z0-9_.-]"), "")
        .take(24).ifBlank { "unknown" }

    fun record(kind: String, screen: String, label: String = "", seconds: Int = 0) {
        // Only enumerated event names are supported; never submit screen contents.
        if (kind !in setOf("launch", "screen", "heartbeat", "camera", "timelapse", "error")) return
        val safeScreen = if (screen in setOf(
                "home", "battle", "history", "profile", "login", "register", "viewer", "inbox"
            )) screen else "other"
        val safeLabel = label.replace(Regex("[^A-Za-z0-9_.-]"), "").take(48)
        val payload = JSONObject()
            .put("event_id", UUID.randomUUID().toString())
            .put("installation_id", installationId)
            .put("kind", kind)
            .put("screen", safeScreen)
            .put("label", safeLabel)
            .put("seconds", seconds.coerceIn(0, 60))
            .put("app_version", appVersion.replace(Regex("[^A-Za-z0-9_.-]"), "").take(32))
            .put("android_version", androidVersion)
        background.execute {
            try {
                api.sendActivity(payload)
            } catch (_: Exception) {
                // Failure must never interrupt gameplay or reveal account information.
            }
        }
    }

    companion object {
        private val background = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "KisaMoreActivityReporter").apply { isDaemon = true }
        }
    }
}
