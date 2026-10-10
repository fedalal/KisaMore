package farm.kisamore.battle

data class HomeClip(val battle: Battle?, val path: String, val isWholeBattle: Boolean, val posterUrl: String? = null)

/** All decisions about the welcome screen are pure and covered by unit tests. */
object HomeBattleSelector {
    fun nextOpenBattle(battles: List<Battle>): Battle? =
        battles.asSequence()
            .filter { it.status == "open" && it.remainingEntries > 0 }
            .sortedWith(
                compareBy<Battle> { it.startDate ?: "9999" }
                    .thenBy { it.remainingEntries }
                    .thenBy { it.createdAt ?: "" }
            )
            .firstOrNull()

    fun videoOptions(battles: List<Battle>, genericClips: List<HomeClip> = emptyList()): List<HomeClip> {
        val clips = mutableListOf<HomeClip>()
        val seen = mutableSetOf<String>()
        fun offer(battle: Battle, path: String?, isWhole: Boolean) {
            if (!path.isNullOrBlank() && seen.add(path)) {
                clips.add(HomeClip(battle, path, isWhole))
            }
        }

        val completed = battles.filter { it.status == "finished" }
            .sortedByDescending { it.finishedAt ?: it.createdAt ?: "" }
        val started = battles.filter { it.status in listOf("growing", "judging", "planting") }

        // Completed whole-shelf timelapse is the first choice, as on the web.
        completed.forEach { battle ->
            battle.cameraViews.sortedByDescending { it.primary }.forEach { camera ->
                offer(battle, camera.timelapseFullUrl, true)
            }
        }
        // If no complete battle video exists, show a single plant's growth.
        completed.forEach { battle ->
            battle.entries.forEach { entry -> offer(battle, entry.timelapseFullUrl, false) }
        }
        (completed + started).forEach { battle ->
            battle.entries.forEach { entry ->
                offer(battle, entry.timelapse3dUrl, false)
                offer(battle, entry.timelapse24hUrl, false)
            }
            battle.cameraViews.sortedByDescending { it.primary }.forEach { camera ->
                offer(battle, camera.timelapse3dUrl, true)
                offer(battle, camera.timelapse24hUrl, true)
            }
        }
        genericClips.forEach { if (seen.add(it.path)) clips.add(it) }
        return clips.take(36)
    }
}
