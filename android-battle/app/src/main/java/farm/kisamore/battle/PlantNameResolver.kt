package farm.kisamore.battle

import org.json.JSONObject

/** Resolve server-provided multilingual crop names in the selected app language. */
internal object PlantNameResolver {
    fun resolve(names: JSONObject?, language: String, fallback: String): String {
        if (names == null) return fallback
        for (code in listOf(language, "en", "ru")) {
            val value = names.optString(code).trim()
            if (value.isNotBlank()) return value
        }
        return fallback
    }
}
