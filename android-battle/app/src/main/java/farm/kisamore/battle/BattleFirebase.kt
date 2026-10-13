package farm.kisamore.battle

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONArray
import org.json.JSONObject

/** Registration is optional until the Firebase Android config is installed. */
object BattleFirebase {
    private const val TAG = "BattleFirebase"
    private const val PREF = "kisamore_battle_api"

    fun refresh(context: Context) {
        val app = context.applicationContext
        if (!ApiClient(app).hasSession()) return
        // Missing google-services.json MUST NOT prevent login or launch.
        try {
            if (FirebaseApp.getApps(app).isEmpty()) {
                if (FirebaseApp.initializeApp(app) == null) return
            }
            FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                if (token.isNotBlank()) register(app, token)
            }.addOnFailureListener {
                Log.w(TAG, "Firebase registration unavailable")
            }
        } catch (_: RuntimeException) {
            Log.w(TAG, "Firebase not configured yet; periodic inbox remains available")
        }
    }

    fun register(context: Context, token: String) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
            .putString("fcm_push_token", token).apply()
        Thread {
            try {
                val api = ApiClient(context.applicationContext)
                if (api.hasSession()) api.registerPushDevice(token)
            } catch (_: Exception) {
                // Retry on resume/login; never log token or account secrets.
                Log.w(TAG, "Push token registration delayed")
            }
        }.start()
    }
}

class BattleFirebaseService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        BattleFirebase.register(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        if (message.data["type"] != "battle_admin_message") return
        val id = message.data["receipt_id"].orEmpty()
        if (id.isBlank()) return
        val api = ApiClient(applicationContext)
        if (!api.hasSession()) return
        // Never trust account ownership from a push received after logout or
        // account switching. The server returns only the current user's inbox.
        try {
            val inbox=api.battleInbox()
            val messages=inbox.optJSONArray("messages") ?: return
            val visible=JSONArray()
            for (i in 0 until messages.length()) {
                val entry=messages.optJSONObject(i) ?: continue
                if (entry.optString("id")==id && entry.isNull("read_at")) {
                    visible.put(entry)
                    break
                }
            }
            if (visible.length()>0)
                BattleInboxJob.notifyNew(applicationContext,
                    JSONObject().put("messages",visible))
        } catch (_: Exception) {
            // Periodic inbox polling remains the reliable fallback.
        }
    }
}
