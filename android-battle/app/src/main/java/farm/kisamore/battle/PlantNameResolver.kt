package farm.kisamore.battle

import org.json.JSONObject

/** Select the plant translation from the user's current application language. */
internal object PlantNameResolver {
    fun translations(names: JSONObject?): Map<String, String> {
        if (names == null) return emptyMap()
        return buildMap {
            val keys = names.keys()
            while (keys.hasNext()) {
                val code = keys.next()
                val value = names.optString(code).trim()
                if (value.isNotEmpty() && value != "null") put(code.lowercase(), value)
            }
        }
    }

    fun resolve(names: JSONObject?, language: String, fallback: String): String =
        resolve(translations(names), language, fallback)

    fun resolve(names: Map<String, String>, language: String, fallback: String): String {
        val selected = language.lowercase().substringBefore('-')
        return sequenceOf(selected, "en", "ru")
            .mapNotNull { names[it]?.trim()?.takeIf { it.isNotEmpty() } }
            .firstOrNull() ?: fallback
    }
}
