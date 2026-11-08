package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object TokenManager {
    private const val PREFS_NAME = "sangam_secure_prefs"
    private const val LEGACY_PREFS = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_AUTH_STATE = "zitadel_auth_state"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"

    private lateinit var prefs: SharedPreferences
    private lateinit var appContext: Context

    fun init(context: Context) {
        appContext = context.applicationContext
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        prefs = EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
        // One-time move off the old plaintext file, then wipe it.
        val legacy = context.getSharedPreferences(LEGACY_PREFS, Context.MODE_PRIVATE)
        val legacyToken = legacy.getString(KEY_TOKEN, null)
        if (!legacyToken.isNullOrEmpty() && prefs.getString(KEY_TOKEN, null).isNullOrEmpty()) {
            prefs.edit()
                .putString(KEY_TOKEN, legacyToken)
                .putString(KEY_ACTOR_ID, legacy.getString(KEY_ACTOR_ID, null))
                .putString(KEY_ACTOR_NAME, legacy.getString(KEY_ACTOR_NAME, null))
                .apply()
        }
        legacy.edit().clear().apply()
    }

    fun appContext(): Context = appContext

    fun readAuthStateJson(): String? = prefs.getString(KEY_AUTH_STATE, null)

    fun saveAuthState(json: String) {
        prefs.edit()
            .putString(KEY_AUTH_STATE, json)
            .remove(KEY_TOKEN)
            .apply()
    }

    fun saveProfile(actorId: String, name: String) {
        prefs.edit()
            .putString(KEY_ACTOR_ID, actorId)
            .putString(KEY_ACTOR_NAME, name)
            .apply()
    }

    fun getToken(): String? {
        val raw = prefs.getString(KEY_AUTH_STATE, null)
        if (!raw.isNullOrEmpty()) {
            return try {
                net.openid.appauth.AuthState.jsonDeserialize(raw).accessToken
            } catch (_: Exception) {
                null
            }
        }
        return prefs.getString(KEY_TOKEN, null)
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    fun getActorId(): String? = prefs.getString(KEY_ACTOR_ID, null)

    fun getActorName(): String? = prefs.getString(KEY_ACTOR_NAME, null)

    fun isLoggedIn(): Boolean = getToken() != null
}
