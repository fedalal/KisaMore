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
        versionCode = 31
        versionName = "0.6.16"
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
