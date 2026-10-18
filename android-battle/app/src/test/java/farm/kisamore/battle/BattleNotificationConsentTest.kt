package farm.kisamore.battle

import android.content.Context
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [32])
class BattleNotificationConsentTest {
    @Test fun promptOnlyAfterLoginAndPersistAcceptOrDecline() {
        val app = RuntimeEnvironment.getApplication()
        val accountPrefs = app.getSharedPreferences("kisamore_battle_api", Context.MODE_PRIVATE)
        val consentPrefs = app.getSharedPreferences("kisamore_battle_notification_consent", Context.MODE_PRIVATE)
        accountPrefs.edit().clear().commit()
        consentPrefs.edit().clear().commit()
        try {
            assertFalse(BattleNotificationConsent.shouldOfferAfterLogin(app))
            accountPrefs.edit().putString("session_cookie", "session=test").commit()
            assertTrue(BattleNotificationConsent.shouldOfferAfterLogin(app))
            BattleNotificationConsent.record(app, false)
            assertTrue(BattleNotificationConsent.wasAnswered(app))
            assertFalse(BattleNotificationConsent.shouldOfferAfterLogin(app))
            assertFalse(BattleNotificationConsent.enabled(app))
            // Same persistent app data after another login or package update.
            accountPrefs.edit().putString("session_cookie", "session=another").commit()
            assertFalse(BattleNotificationConsent.shouldOfferAfterLogin(app))
            BattleNotificationConsent.record(app, true)
            assertTrue(BattleNotificationConsent.enabled(app))
            assertFalse(BattleNotificationConsent.shouldOfferAfterLogin(app))
        } finally {
            accountPrefs.edit().clear().commit()
            consentPrefs.edit().clear().commit()
        }
    }

    @Test fun consentDialogUsesEverySupportedAppLanguage() {
        val app = RuntimeEnvironment.getApplication()
        val settings = app.getSharedPreferences("battle_settings", Context.MODE_PRIVATE)
        val legacy = app.getSharedPreferences("kisamore_battle_language", Context.MODE_PRIVATE)
        val old = settings.getString("language", null)
        val oldLegacy = legacy.getString("language", null)
        try {
            for ((code, _) in AppLanguage.supported) {
                AppLanguage.set(app, code)
                assertEquals(code, AppLanguage(app).code)
                for (message in listOf(
                    "Включить уведомления?",
                    "Получайте сообщения о битвах, действиях с растениями и результатах прямо на телефон. Вы сможете изменить это решение в настройках.",
                    "Включить", "Не сейчас", "Разрешить уведомления"
                )) {
                    val translated = AppLanguage(app).t(message)
                    assertTrue("Missing $code translation for $message", translated.isNotBlank())
                    if (code != "ru") assertTrue("Missing translation for $code: $message", translated != message)
                }
            }
        } finally {
            val edit = settings.edit()
            if (old == null) edit.remove("language") else edit.putString("language", old)
            edit.commit()
            val leg = legacy.edit()
            if (oldLegacy == null) leg.remove("language") else leg.putString("language", oldLegacy)
            leg.commit()
        }
    }
}
