package com.sangam.app.network

import android.content.Context
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.tasks.Task
import com.google.android.gms.tasks.Tasks
import com.google.firebase.FirebaseNetworkException
import com.google.firebase.FirebaseTooManyRequestsException
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseAuthException
import com.google.firebase.auth.FirebaseAuthInvalidCredentialsException
import com.google.firebase.auth.FirebaseAuthInvalidUserException
import com.google.firebase.auth.FirebaseAuthUserCollisionException
import com.google.firebase.auth.FirebaseAuthWeakPasswordException
import com.google.firebase.auth.GoogleAuthProvider
import com.google.firebase.auth.UserProfileChangeRequest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import retrofit2.HttpException
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Sign-in for the Android app. Firebase Authentication holds the account
 * (Google or email/password) and refreshes the session; the backend verifies
 * the Firebase ID token on every request and links a Sangam actor to it.
 *
 * No password and no long-lived token is stored by Sangam. Firebase keeps a
 * refresh token in its own private storage and hands out one-hour ID tokens.
 */
object FirebaseSession {

    data class Result(val actorId: String, val name: String, val email: String?, val isNewUser: Boolean)

    class AuthFailure(message: String) : Exception(message)

    private fun auth(): FirebaseAuth? = try {
        FirebaseAuth.getInstance()
    } catch (_: Exception) {
        null
    }

    fun isSignedIn(): Boolean = auth()?.currentUser != null

    /**
     * The OAuth web client id Firebase generates when Google sign-in is
     * enabled. The Google Services plugin writes it to `default_web_client_id`
     * from google-services.json; it is looked up by name so the app still
     * builds before that file is refreshed.
     */
    fun googleWebClientId(context: Context): String? {
        val id = context.resources.getIdentifier("default_web_client_id", "string", context.packageName)
        if (id != 0) {
            val value = context.getString(id).trim()
            if (value.isNotEmpty()) return value
        }
        val fromBuild = com.sangam.app.BuildConfig.GOOGLE_WEB_CLIENT_ID.trim()
        return fromBuild.ifEmpty { null }
    }

    fun googleSignInOptions(context: Context): GoogleSignInOptions? {
        val clientId = googleWebClientId(context) ?: return null
        return GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestIdToken(clientId)
            .requestEmail()
            .requestProfile()
            .build()
    }

    suspend fun signInWithGoogle(googleIdToken: String): Result {
        val auth = auth() ?: throw AuthFailure("Sign-in is not available on this device.")
        val credential = GoogleAuthProvider.getCredential(googleIdToken, null)
        val result = mapErrors { auth.signInWithCredential(credential).await() }
        return linkWithBackend(isNewUser = result.additionalUserInfo?.isNewUser == true)
    }

    suspend fun signInWithEmail(email: String, password: String): Result {
        val auth = auth() ?: throw AuthFailure("Sign-in is not available on this device.")
        mapErrors { auth.signInWithEmailAndPassword(email, password).await() }
        return linkWithBackend(isNewUser = false)
    }

    suspend fun signUpWithEmail(name: String, email: String, password: String): Result {
        val auth = auth() ?: throw AuthFailure("Sign-up is not available on this device.")
        val result = mapErrors { auth.createUserWithEmailAndPassword(email, password).await() }
        val user = result.user ?: throw AuthFailure("Could not create the account. Try again.")
        mapErrors {
            user.updateProfile(UserProfileChangeRequest.Builder().setDisplayName(name).build()).await()
        }
        // Best effort. The account works before the address is verified.
        try {
            user.sendEmailVerification().await()
        } catch (_: Exception) {
        }
        // Force a fresh ID token so it carries the display name just set.
        mapErrors { user.getIdToken(true).await() }
        return linkWithBackend(isNewUser = true)
    }

    suspend fun sendPasswordReset(email: String) {
        val auth = auth() ?: throw AuthFailure("Password reset is not available on this device.")
        mapErrors { auth.sendPasswordResetEmail(email).await() }
    }

    /** Current ID token for a suspend caller. Refreshes it when it is near expiry. */
    suspend fun idToken(forceRefresh: Boolean = false): String? {
        val user = auth()?.currentUser ?: return null
        return try {
            user.getIdToken(forceRefresh).await().token
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Current ID token for OkHttp interceptors, which run on a background
     * thread. Firebase returns its cached token unless it is about to expire.
     */
    fun idTokenBlocking(forceRefresh: Boolean = false): String? {
        val user = auth()?.currentUser ?: return null
        return try {
            Tasks.await(user.getIdToken(forceRefresh), 15, TimeUnit.SECONDS).token
        } catch (_: Exception) {
            null
        }
    }

    /**
     * After the backend has deleted the account's data, remove the Firebase
     * login too, then sign out. Firebase may refuse if the last sign-in was
     * long ago; the backend account is already deactivated either way.
     */
    suspend fun deleteLoginAndSignOut(context: Context) {
        try {
            auth()?.currentUser?.delete()?.await()
        } catch (_: Exception) {
        }
        signOut(context)
    }

    fun signOut(context: Context) {
        try {
            auth()?.signOut()
        } catch (_: Exception) {
        }
        try {
            // Clear the cached Google account so the picker shows next time.
            GoogleSignIn.getClient(context, GoogleSignInOptions.DEFAULT_SIGN_IN).signOut()
        } catch (_: Exception) {
        }
        try {
            com.sangam.app.billing.Billing.logOut()
        } catch (_: Exception) {
        }
        RealtimeClient.stop()
        TokenManager.clear()
    }

    /** Create or load the Sangam actor for the signed-in Firebase user. */
    private suspend fun linkWithBackend(isNewUser: Boolean): Result {
        val me = try {
            ApiClient.authApi.me()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Leave no half-signed-in state behind: without an actor the app
            // cannot work, so the user starts the sign-in again.
            auth()?.signOut()
            throw AuthFailure(
                when {
                    e is HttpException && (e.code() == 401 || e.code() == 403) ->
                        "The server did not accept this sign-in. Please try again, or contact support if it keeps happening."
                    e is HttpException ->
                        "The server had a problem (HTTP ${e.code()}). Please try again in a moment."
                    e is IOException ->
                        "Could not reach Sangam. Check your internet connection and try again."
                    else -> "Sign-in failed. Please try again."
                }
            )
        }
        val email = me.email ?: auth()?.currentUser?.email
        TokenManager.saveProfile(me.actor_id, me.name, email)
        // Purchases are credited to this actor by the backend webhook.
        com.sangam.app.billing.Billing.logIn(me.actor_id)
        return Result(me.actor_id, me.name, email, isNewUser)
    }

    private suspend fun <T> mapErrors(block: suspend () -> T): T = try {
        block()
    } catch (e: AuthFailure) {
        throw e
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        throw AuthFailure(friendlyMessage(e))
    }

    fun friendlyMessage(e: Exception): String = when (e) {
        is FirebaseAuthWeakPasswordException -> "Choose a stronger password (at least 6 characters)."
        is FirebaseAuthUserCollisionException ->
            "An account already exists for this email. Sign in instead, or use Continue with Google if you signed up with Google."
        is FirebaseAuthInvalidUserException -> when (e.errorCode) {
            "ERROR_USER_DISABLED" -> "This account has been disabled. Contact support."
            else -> "No account found for this email. Tap Sign Up to create one."
        }
        is FirebaseAuthInvalidCredentialsException -> when (e.errorCode) {
            "ERROR_INVALID_EMAIL" -> "Enter a valid email address."
            else -> "Email or password is incorrect."
        }
        is FirebaseTooManyRequestsException -> "Too many attempts. Wait a few minutes and try again."
        is FirebaseNetworkException -> "No internet connection. Check your network and try again."
        is FirebaseAuthException -> when (e.errorCode) {
            "ERROR_OPERATION_NOT_ALLOWED" ->
                "This sign-in method is not enabled yet. Please try another option."
            else -> e.localizedMessage ?: "Sign-in failed. Please try again."
        }
        else -> e.localizedMessage ?: "Sign-in failed. Please try again."
    }
}

private suspend fun <T> Task<T>.await(): T = suspendCancellableCoroutine { cont ->
    addOnCompleteListener { task ->
        val error = task.exception
        when {
            error != null -> cont.resumeWithException(error)
            task.isCanceled -> cont.cancel()
            else -> cont.resume(task.result)
        }
    }
}
