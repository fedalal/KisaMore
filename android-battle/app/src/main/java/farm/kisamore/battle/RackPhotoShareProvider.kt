package farm.kisamore.battle

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import java.io.File
import java.io.FileNotFoundException

/** Shares only generated JPEGs, not arbitrary files under app storage. */
class RackPhotoShareProvider : ContentProvider() {
    override fun onCreate() = true
    override fun getType(uri: Uri): String? = if (validFile(uri) != null) "image/jpeg" else null
    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw FileNotFoundException("Read only")
        val file = validFile(uri) ?: throw FileNotFoundException("Invalid photo")
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
    }
    private fun validFile(uri: Uri): File? {
        if (uri.authority != "${context?.packageName}.photos") return null
        val parts = uri.pathSegments
        if (parts.size != 2 || parts[0] != "shared") return null
        val name = parts[1]
        if (!name.matches(Regex("[a-zA-Z0-9_-]{1,64}\\.jpg"))) return null
        val file = File(context?.cacheDir, "shared_photos/$name")
        return file.takeIf { it.isFile }
    }
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
                       selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?,
                        selectionArgs: Array<out String>?): Int = 0
}
