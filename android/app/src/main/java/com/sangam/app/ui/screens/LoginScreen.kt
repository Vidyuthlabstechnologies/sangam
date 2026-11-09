package com.sangam.app.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.auth.api.signin.GoogleSignInStatusCodes
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.sangam.app.R
import com.sangam.app.network.FirebaseSession
import com.sangam.app.network.RealtimeClient
import com.sangam.app.ui.components.LegalFooter
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(onLoginSuccess: (isNewUser: Boolean) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    var isLogin by remember { mutableStateOf(true) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isPasswordFocused by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }

    fun finishSignIn(result: FirebaseSession.Result, provider: String) {
        syncFirestoreProfile(result.actorId, result.email.orEmpty(), result.name, provider)
        RealtimeClient.start()
        onLoginSuccess(result.isNewUser)
    }

    // Google Sign-In asks for an ID token that Firebase exchanges for a session.
    val googleSignInClient = remember {
        FirebaseSession.googleSignInOptions(context)?.let { GoogleSignIn.getClient(context, it) }
    }

    val googleLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val account = try {
            GoogleSignIn.getSignedInAccountFromIntent(result.data).getResult(ApiException::class.java)
        } catch (e: ApiException) {
            error = when (e.statusCode) {
                GoogleSignInStatusCodes.SIGN_IN_CANCELLED -> null
                CommonStatusCodes.NETWORK_ERROR -> "No internet connection. Check your network and try again."
                CommonStatusCodes.DEVELOPER_ERROR ->
                    "Google Sign-In is not set up for this build of the app. Please sign in with email for now."
                else -> "Google Sign-In did not complete (code ${e.statusCode}). Please try again."
            }
            return@rememberLauncherForActivityResult
        }
        val idToken = account?.idToken
        if (idToken.isNullOrBlank()) {
            error = "Google did not return a sign-in token. Please try again."
            return@rememberLauncherForActivityResult
        }
        scope.launch {
            loading = true
            error = null
            try {
                finishSignIn(FirebaseSession.signInWithGoogle(idToken), "google")
            } catch (e: Exception) {
                googleSignInClient?.signOut()
                error = e.message ?: "Google Sign-In failed. Please try again."
            } finally {
                loading = false
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                "Sangam",
                style = MaterialTheme.typography.displayMedium,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                "Deploy Autonomous Voice Agents in Seconds",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(12.dp))

            // Witty Duolingo-style Mascot Speech Bubble (Clean White Theme)
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
            ) {
                Text(
                    text = if (isPasswordFocused) {
                        "Psst! Enter your master password. I've got my wings over my eyes, totally not peeking!"
                    } else {
                        "Namaste, ${if (name.isNotBlank()) name else "Boss"}! Ready to deploy autonomous Indian voice agents?"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 100% Transparent Mascot (No background box!)
            Image(
                painter = painterResource(
                    id = if (isPasswordFocused) R.drawable.mascot_kite_peekaboo else R.drawable.mascot_kite_idle
                ),
                contentDescription = "Kite Master Mascot",
                modifier = Modifier
                    .size(120.dp)
                    .padding(bottom = 4.dp),
                contentScale = ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {

                    // Google Sign-In Button
                    OutlinedButton(
                        onClick = {
                            error = null
                            info = null
                            val client = googleSignInClient
                            if (client == null) {
                                error = "Google Sign-In is not set up for this build of the app. Please sign in with email for now."
                            } else {
                                // Start from a clean slate so the account picker always shows.
                                client.signOut().addOnCompleteListener {
                                    googleLauncher.launch(client.signInIntent)
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        enabled = !loading,
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                        ),
                    ) {
                        Image(
                            painter = painterResource(R.drawable.ic_google_logo),
                            contentDescription = "Google",
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            "Continue with Google",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Divider with text
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        HorizontalDivider(modifier = Modifier.weight(1f))
                        Text(
                            "  or continue with email  ",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.outline,
                        )
                        HorizontalDivider(modifier = Modifier.weight(1f))
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    if (!isLogin) {
                        OutlinedTextField(
                            value = name,
                            onValueChange = { name = it },
                            label = { Text("Full Name") },
                            leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Email") },
                        leadingIcon = { Icon(Icons.Default.Email, contentDescription = null) },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Next,
                        ),
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Password") },
                        leadingIcon = { Icon(Icons.Default.Lock, contentDescription = null) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { isPasswordFocused = it.isFocused },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done,
                        ),
                    )

                    val displayError = error
                    if (displayError != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = displayError,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    val displayInfo = info
                    if (displayInfo != null && displayError == null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = displayInfo,
                            color = MaterialTheme.colorScheme.primary,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    Button(
                        onClick = {
                            val cleanEmail = email.trim()
                            val cleanName = name.trim()
                            error = null
                            info = null
                            when {
                                cleanEmail.isEmpty() || password.isEmpty() -> {
                                    error = "Please enter email and password"
                                    return@Button
                                }
                                !android.util.Patterns.EMAIL_ADDRESS.matcher(cleanEmail).matches() -> {
                                    error = "Enter a valid email address."
                                    return@Button
                                }
                                !isLogin && cleanName.isEmpty() -> {
                                    error = "Please enter your name"
                                    return@Button
                                }
                                !isLogin && password.length < 8 -> {
                                    error = "Use at least 8 characters for your password."
                                    return@Button
                                }
                            }
                            loading = true
                            scope.launch {
                                try {
                                    val result = if (isLogin) {
                                        FirebaseSession.signInWithEmail(cleanEmail, password)
                                    } else {
                                        FirebaseSession.signUpWithEmail(cleanName, cleanEmail, password)
                                    }
                                    finishSignIn(result, "password")
                                } catch (e: Exception) {
                                    error = e.message ?: "Sign-in failed. Please try again."
                                } finally {
                                    loading = false
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        enabled = !loading,
                    ) {
                        if (loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = MaterialTheme.colorScheme.onPrimary,
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Text(
                                if (isLogin) "Sign In" else "Create Account",
                                style = MaterialTheme.typography.labelLarge,
                            )
                        }
                    }

                    if (isLogin) {
                        TextButton(
                            onClick = {
                                val cleanEmail = email.trim()
                                error = null
                                info = null
                                if (!android.util.Patterns.EMAIL_ADDRESS.matcher(cleanEmail).matches()) {
                                    error = "Enter your email above, then tap Forgot password."
                                    return@TextButton
                                }
                                scope.launch {
                                    try {
                                        FirebaseSession.sendPasswordReset(cleanEmail)
                                        info = "If an account exists for $cleanEmail, a reset link is on its way."
                                    } catch (e: Exception) {
                                        error = e.message
                                    }
                                }
                            },
                            enabled = !loading,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Forgot password?", style = MaterialTheme.typography.bodySmall)
                        }
                    } else {
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    TextButton(
                        onClick = {
                            isLogin = !isLogin
                            error = null
                            info = null
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            if (isLogin) "Don't have an account? Sign Up" else "Already have an account? Sign In",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "By continuing you agree to the Terms of use and Privacy policy.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            LegalFooter()
        }
    }
}

private fun syncFirestoreProfile(actorId: String, email: String, name: String, provider: String) {
    val firebaseUser = try {
        FirebaseAuth.getInstance().currentUser
    } catch (_: Exception) {
        null
    } ?: return
    try {
        val userDoc = hashMapOf(
            "uid" to firebaseUser.uid,
            "actorId" to actorId,
            "email" to email,
            "name" to name,
            "authProvider" to provider,
            "lastLogin" to FieldValue.serverTimestamp(),
        )
        FirebaseFirestore.getInstance()
            .collection("users")
            .document(firebaseUser.uid)
            .set(userDoc, SetOptions.merge())
    } catch (_: Exception) {
    }
}
