package com.sangam.app.ui.screens

import android.app.Activity
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
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import com.sangam.app.network.LoginRequest
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.RegisterRequest
import com.sangam.app.network.TokenManager
import com.sangam.app.network.TokenResponse
import com.sangam.app.network.ZitadelAuth
import kotlinx.coroutines.launch
import retrofit2.HttpException

@Composable
fun LoginScreen(onLoginSuccess: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    val zitadelLoggedIn by ZitadelAuth.loggedIn.collectAsState()
    val zitadelError by ZitadelAuth.error.collectAsState()

    LaunchedEffect(zitadelLoggedIn) {
        if (zitadelLoggedIn) {
            onLoginSuccess()
        }
    }

    var isLogin by remember { mutableStateOf(true) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isPasswordFocused by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Server Configuration State
    var showServerConfig by remember { mutableStateOf(false) }
    var serverUrlInput by remember { mutableStateOf(TokenManager.getServerUrl()) }
    var serverConfigSaved by remember { mutableStateOf(false) }

    // Google Sign-In Client
    val googleSignInClient = remember {
        val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestProfile()
            .build()
        GoogleSignIn.getClient(context, gso)
    }

    // Google Sign-In Activity Result Launcher
    val googleLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
        try {
            val account = task.getResult(ApiException::class.java)
            if (account != null) {
                scope.launch {
                    loading = true
                    error = null
                    try {
                        val accountName = account.displayName ?: account.givenName ?: "Google User"
                        val accountEmail = account.email?.trim().orEmpty()
                        if (accountEmail.isEmpty()) {
                            error = "Google did not share an email address. Sign in with email and password."
                            return@launch
                        }
                        val secret = TokenManager.googleLinkSecret(accountEmail)
                        if (secret.isEmpty()) {
                            error = "Could not store this sign-in on the device."
                            return@launch
                        }
                        val resp = try {
                            linkGoogleAccount(accountEmail, accountName, secret)
                        } catch (e: Exception) {
                            error = friendlyAuthError(e)
                            return@launch
                        }
                        syncFirestoreProfile(resp.actor_id, accountEmail, resp.name, "google")
                        TokenManager.saveToken(resp.access_token, resp.actor_id, resp.name, accountEmail)
                        try {
                            RealtimeClient.start()
                        } catch (_: Exception) {}
                        onLoginSuccess()
                    } catch (e: Exception) {
                        error = friendlyAuthError(e)
                    } finally {
                        loading = false
                    }
                }
            }
        } catch (e: ApiException) {
            error = "Google Sign-In status ${e.statusCode}: ${e.message ?: "Sign-in was cancelled"}"
        } catch (e: Exception) {
            error = "Google Sign-In failed: ${e.message}"
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp, vertical = 24.dp),
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
                "AI Calling Agents Powered by Sarvam AI",
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
                            googleLauncher.launch(googleSignInClient.signInIntent)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        enabled = !loading,
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                        ),
                    ) {
                        Icon(
                            Icons.Default.AccountCircle,
                            contentDescription = "Google",
                            tint = MaterialTheme.colorScheme.primary,
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

                    Spacer(modifier = Modifier.height(8.dp))

                    // Zitadel SSO Button (Self-Hosted Identity)
                    OutlinedButton(
                        onClick = {
                            (context as? Activity)?.let { ZitadelAuth.start(it) }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        enabled = !loading,
                    ) {
                        Icon(
                            Icons.Default.Security,
                            contentDescription = "Zitadel SSO",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            "Continue with Zitadel SSO",
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // Divider with text
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        HorizontalDivider(modifier = Modifier.weight(1f))
                        Text(
                            "  or password  ",
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

                    val displayError = error ?: zitadelError
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

                    Spacer(modifier = Modifier.height(16.dp))

                    Button(
                        onClick = {
                            if (email.isBlank() || password.isBlank()) {
                                error = "Please enter email and password"
                                return@Button
                            }
                            if (!isLogin && name.isBlank()) {
                                error = "Please enter your name"
                                return@Button
                            }
                            loading = true
                            error = null
                            scope.launch {
                                try {
                                    val resp: TokenResponse = if (isLogin) {
                                        ApiClient.authApi.login(LoginRequest(email.trim(), password))
                                    } else {
                                        ApiClient.authApi.register(RegisterRequest(name.trim(), email.trim(), password))
                                    }
                                    TokenManager.saveToken(resp.access_token, resp.actor_id, resp.name, email.trim())
                                    try {
                                        RealtimeClient.start()
                                    } catch (_: Exception) {}
                                    onLoginSuccess()
                                } catch (e: Exception) {
                                    error = friendlyAuthError(e)
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

                    Spacer(modifier = Modifier.height(8.dp))

                    TextButton(
                        onClick = {
                            isLogin = !isLogin
                            error = null
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

            Spacer(modifier = Modifier.height(14.dp))

            // Expandable Server Connection Configuration
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    TextButton(
                        onClick = { showServerConfig = !showServerConfig },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.Dns, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Server Connection Settings",
                            style = MaterialTheme.typography.labelLarge,
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        Icon(
                            imageVector = if (showServerConfig) Icons.Default.ArrowDropUp else Icons.Default.ArrowDropDown,
                            contentDescription = null,
                        )
                    }

                    AnimatedVisibility(visible = showServerConfig) {
                        Column(modifier = Modifier.padding(top = 8.dp)) {
                            Text(
                                "Target Backend URL:",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = serverUrlInput,
                                onValueChange = {
                                    serverUrlInput = it
                                    serverConfigSaved = false
                                },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true,
                                placeholder = { Text("http://192.168.0.x:8000") },
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Button(
                                    onClick = {
                                        if (TokenManager.saveServerUrl(serverUrlInput)) {
                                            serverUrlInput = TokenManager.getServerUrl()
                                            serverConfigSaved = true
                                            error = null
                                        } else {
                                            serverConfigSaved = false
                                            error = "Enter a full http:// or https:// server URL."
                                        }
                                    },
                                    modifier = Modifier.height(36.dp),
                                ) {
                                    Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("Apply URL", style = MaterialTheme.typography.labelMedium)
                                }
                                if (serverConfigSaved) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        "Saved!",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.primary,
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                "Note: On a physical phone, 10.0.2.2 is not reachable. Use your computer's Wi-Fi address (for example http://192.168.0.103:8000). Google sign-in still needs this server.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.outline,
                            )
                        }
                    }
                }
            }
        }
    }
}

private suspend fun linkGoogleAccount(email: String, name: String, secret: String): TokenResponse {
    try {
        return ApiClient.authApi.login(LoginRequest(email = email, password = secret))
    } catch (loginError: HttpException) {
        if (loginError.code() != 401) throw loginError
    }
    try {
        return ApiClient.authApi.register(RegisterRequest(name = name, email = email, password = secret))
    } catch (registerError: HttpException) {
        if (registerError.code() == 409) {
            throw IllegalStateException("This email already has a password. Sign in with email instead.")
        }
        throw registerError
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

private fun friendlyAuthError(e: Exception): String {
    val raw = when (e) {
        is HttpException -> e.response()?.errorBody()?.string()?.let { body ->
            Regex(""""detail"\s*:\s*"([^"]+)"""").find(body)?.groupValues?.get(1)
        } ?: e.message
        else -> e.message
    } ?: "Authentication failed"
    return if (raw.contains("10.0.2.2") || raw.contains("CLEARTEXT", ignoreCase = true) || raw.contains("failed to connect")) {
        "Could not reach backend at ${TokenManager.getServerUrl()}. On a phone, open Server Connection Settings and enter your computer's http:// address."
    } else {
        raw
    }
}
