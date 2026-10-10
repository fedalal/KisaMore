package farm.kisamore.battle

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
class PlantNameResolverTest {
    @Test fun russianAppPrefersRussianPlantNameInsteadOfEnglishApiDefault() {
        val names = JSONObject("""{"en":"Arugula","ru":"Рукола","zh":"芝麻菜"}""")
        assertEquals("Рукола", PlantNameResolver.resolve(names, "ru", "Arugula"))
        assertEquals("芝麻菜", PlantNameResolver.resolve(names, "zh", "Arugula"))
        assertEquals("Arugula", PlantNameResolver.resolve(names, "en", "Arugula"))
    }

    @Test fun gracefullyFallsBackWhenTranslationMissing() {
        val names = JSONObject("""{"en":"Radish","ru":"Редис"}""")
        assertEquals("Radish", PlantNameResolver.resolve(names, "de", "Default"))
        assertEquals("Default", PlantNameResolver.resolve(JSONObject(), "ru", "Default"))
        assertEquals("Default", PlantNameResolver.resolve(null, "ru", "Default"))
    }

    @Test fun authLabelsRespectSelectedEnglishLanguage() {
        val ctx = RuntimeEnvironment.getApplication()
        ctx.getSharedPreferences("battle_settings", 0).edit()
            .putString("language", "en").commit()
        val language = AppLanguage(ctx)
        assertEquals("BATTLE SIGN IN", language.t("ВХОД В BATTLE"))
        assertEquals("Create account", language.t("Создать аккаунт"))
        assertEquals("Close", language.t("Закрыть окно"))
        assertEquals("Password", language.t("Пароль"))
        assertEquals("Enter email and password", language.t("Введите email и пароль"))
    }
}
