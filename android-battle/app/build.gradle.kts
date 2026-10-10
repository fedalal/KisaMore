plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "farm.kisamore.battle"
    compileSdk = 36

    defaultConfig {
        applicationId = "farm.kisamore.battle"
        minSdk = 26
        targetSdk = 36
        versionCode = 32
        versionName = "0.6.17"
    }

    // Google Play: use the EXISTING upload keystore. Missing credentials must
    // never cause a production release to be signed with a different key.
    val uploadStoreFile = System.getenv("KISAMORE_UPLOAD_STORE_FILE")
    val uploadStorePassword = System.getenv("KISAMORE_UPLOAD_STORE_PASSWORD")
    val uploadKeyAlias = System.getenv("KISAMORE_UPLOAD_KEY_ALIAS")
    val uploadKeyPassword = System.getenv("KISAMORE_UPLOAD_KEY_PASSWORD")

    signingConfigs {
        create("release") {
            if (
                !uploadStoreFile.isNullOrBlank() &&
                !uploadStorePassword.isNullOrBlank() &&
                !uploadKeyAlias.isNullOrBlank() &&
                !uploadKeyPassword.isNullOrBlank()
            ) {
                storeFile = file(uploadStoreFile)
                storePassword = uploadStorePassword
                keyAlias = uploadKeyAlias
                keyPassword = uploadKeyPassword
            }
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            if (!uploadStoreFile.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("com.google.zxing:core:3.5.3")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}

// Fail closed: release artifacts are NEVER generated without the original
// Google Play upload key. Debug builds and tests need no signing secrets.
gradle.taskGraph.whenReady {
    // Only this explicitly opted-in CI task may produce an UNSIGNED AAB
    // for manual signing. Play release requires the permanent upload key.
    val offlineUnsigned = System.getenv("KISAMORE_BUILD_UNSIGNED_BUNDLE_FOR_OFFLINE_SIGNING") == "true"
    if (!offlineUnsigned && allTasks.any {
        it.path in setOf(":app:bundleRelease", ":app:assembleRelease")
    }) {
        val required = listOf(
            "KISAMORE_UPLOAD_STORE_FILE",
            "KISAMORE_UPLOAD_STORE_PASSWORD",
            "KISAMORE_UPLOAD_KEY_ALIAS",
            "KISAMORE_UPLOAD_KEY_PASSWORD",
        )
        val missing = required.filter { System.getenv(it).isNullOrBlank() }
        check(missing.isEmpty()) {
            "Google Play release signing requires the original upload keystore: " +
                missing.joinToString(", ")
        }
    }
}
