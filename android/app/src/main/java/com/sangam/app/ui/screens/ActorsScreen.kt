package com.sangam.app.ui.screens

import com.sangam.app.R
import com.sangam.app.ui.components.str

import androidx.compose.ui.text.style.TextOverflow
import com.sangam.app.ui.components.humanize
import com.sangam.app.ui.components.StatusLabel
import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.ActorResponse

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ActorsScreen(onBack: () -> Unit = {}) {
    var actors by remember { mutableStateOf<List<ActorResponse>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            actors = ApiClient.api.listActors()
        } catch (e: Exception) {
            error = friendlyError(e, str(R.string.load_people))
        }
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(str(R.string.people_and_agents)) },
                navigationIcon = { BackButton(onBack) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
            )
        }
    ) { padding ->
        when {
            loading -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            error != null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                ErrorState(error!!, onRetry = null)
            }
            actors.isEmpty() -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { Text(str(R.string.no_people_or_agents_yet)) }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(actors, key = { it.id }) { a ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            border = CardDefaults.outlinedCardBorder(),
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(16.dp),
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(a.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    Text(
                                        actorTypeLabel(a.type),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    a.email?.let {
                                        Text(
                                            it,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    }
                                }
                                if (a.is_active) {
                                    StatusLabel(str(R.string.active))
                                } else {
                                    StatusLabel(
                                        str(R.string.inactive),
                                        container = MaterialTheme.colorScheme.surfaceContainerHigh,
                                        content = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

fun actorTypeLabel(type: String): String = when (type.lowercase()) {
    "human" -> str(R.string.person)
    "ai_agent" -> str(R.string.ai_agent)
    "system" -> str(R.string.connected_app)
    else -> humanize(type)
}
