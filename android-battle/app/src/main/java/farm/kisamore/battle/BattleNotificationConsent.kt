package farm.kisamore.battle

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build

/**
 * One opt-in per app installation. SharedPreferences and the Android runtime
 * permission survive a normal update with the SAME applicationId/signing key.
 * Declining does not nag users at every login; profile settings allow retry.
 */
internal object BattleNotificationConsent {
    private const val STORE = "kisamore_battle_notification_consent"
    private const val ANSWERED = "answered"
    private const val ENABLED = "enabled"

    fun wasAnswered(context: Context): Boolean =
        context.getSharedPreferences(STORE, Context.MODE_PRIVATE).getBoolean(ANSWERED, false)

    fun record(context: Context, enabled: Boolean) {
        context.getSharedPreferences(STORE, Context.MODE_PRIVATE).edit()
            .putBoolean(ANSWERED, true).putBoolean(ENABLED, enabled).apply()
    }

    fun grantedBySystem(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED) return false
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        return manager?.areNotificationsEnabled() != false
    }

    fun enabled(context: Context): Boolean =
        context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .getBoolean(ENABLED, false) && grantedBySystem(context)

    fun shouldOfferAfterLogin(context: Context): Boolean {
        if (!ApiClient(context.applicationContext).hasSession()) return false
        if (wasAnswered(context)) return false
        // Existing installs may already have allowed notifications. Preserve
        // their consent instead of showing the permission prompt again.
        if (Build.VERSION.SDK_INT >= 33 && grantedBySystem(context)) {
            record(context, true)
            return false
        }
        return true
    }
}
