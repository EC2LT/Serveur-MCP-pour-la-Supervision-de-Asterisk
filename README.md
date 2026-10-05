## Description
Le projet MCP Asterisk Supervisor est un système de supervision et de pilotage intelligent d'un serveur de téléphonie VoIP Asterisk 22 LTS. Il expose les capacités techniques d'Asterisk (ARI et AMI) à un LLM local via le Model Context Protocol (MCP), ce qui permet à un utilisateur de dialoguer en langage naturel — par texte ou par la voix — pour consulter l'état du serveur et, selon ses droits, exécuter des actions de pilotage.

L'architecture repose sur trois piliers :

Asterisk : le central téléphonique qui gère les appels, les extensions SIP, les files d'attente et les trunks.

Un serveur MCP (server.py) qui expose des outils (fonctions Python) permettant d'interroger ou de piloter Asterisk via son API REST (ARI).

Deux agents : un agent texte (agent.py) et un agent vocal (vocal_agent.py) qui utilisent un LLM local (Ollama + Qwen 2.5) pour comprendre les demandes et invoquer les outils MCP.

La sécurité est assurée par Keycloak (OIDC/JWT) avec un contrôle d'accès basé sur les rôles (RBAC) : admin, supervisor, operator. Toutes les actions sont tracées dans un journal d'audit.



## Architecture du projet

| Composant | Rôle |
|:---|:---|
| `agent.py` | Agent CLI. L'utilisateur s'authentifie via Keycloak, puis dialogue en texte. Le LLM appelle les outils MCP en fonction de la demande. Une validation humaine est requise pour les outils critiques. |
| `vocal_agent.py` | Agent vocal (Speech-to-Speech). Reçoit les appels Asterisk, transcrit la voix avec Whisper, interroge le LLM, invoque les outils MCP, puis synthétise la réponse avec Piper. |
| `server.py` | Serveur MCP central. Expose les outils, vérifie le JWT et applique le RBAC avant chaque exécution. Lance les modules d'outils. |
| `config/` | Configuration centralisée : variables d'environnement et logging. |
| `security/` | Authentification JWT avec Keycloak, gestion du contexte utilisateur et du RBAC. |
| `asterisk/` | Clients d'accès à Asterisk : ARI (REST/WebSocket) et CDR (MySQL). |
| `tools/` | Définition des outils MCP : supervision, analyse et pilotage. |
| `s2s/` | Pipeline Speech-to-Speech : Whisper (STT) et Piper (TTS). |
| `models/` | Modèles de voix Piper sous forme de fichiers `.onnx`. |
| `logs/` | Journal d'audit contenant les traces de toutes les exécutions d'outils. |
| `tests/` | Scénarios SIPp pour les tests de charge et tests unitaires. |


### 2.3. Flux d'une requête texte — `agent.py`

Le flux d'une requête texte se déroule comme suit :

1. L'utilisateur lance `python3 agent.py` et s'authentifie auprès de **Keycloak** avec son login et son mot de passe.
2. **Keycloak** authentifie l'utilisateur et renvoie un **JWT** contenant notamment ses rôles.
3. L'agent transmet le JWT au **serveur MCP** via la variable `MCP_AUTH_TOKEN`.
4. L'utilisateur saisit une question en français, par exemple :

   > « Combien d'appels sont en cours ? »

5. Le **LLM local (Ollama + Qwen 2.5)** analyse la demande et détermine l'outil MCP approprié, par exemple `list_active_channels`.
6. Si l'outil demandé est considéré comme **critique**, par exemple `hangup_channel`, l'agent demande une **confirmation humaine** avant son exécution.
7. Le **serveur MCP** vérifie le JWT, contrôle les autorisations de l'utilisateur via le **RBAC**, puis autorise ou refuse l'exécution de l'outil.
8. L'outil autorisé interroge **Asterisk via ARI** et récupère les informations demandées.
9. Le résultat est transmis au LLM, qui formule une réponse en français compréhensible par l'utilisateur.
10. L'ensemble de l'exécution est enregistré dans le journal d'audit :

```text
logs/audit.log
```

#### Schéma du flux

```text
Utilisateur
     │
     ▼
agent.py
     │
     │ Authentification
     ▼
 Keycloak
     │
     │ JWT + rôles
     ▼
 Agent CLI
     │
     │ MCP_AUTH_TOKEN
     ▼
 Serveur MCP
     │
     │ Vérification JWT + RBAC
     ▼
 Outil MCP
     │
     │ ARI
     ▼
 Asterisk
     │
     │ Résultat
     ▼
 Serveur MCP
     │
     ▼
 LLM (Ollama + Qwen 2.5)
     │
     ▼
 Réponse en français
     │
     ▼
 Utilisateur

     └──► logs/audit.log
```

---

### 2.4. Flux d'une requête vocale — `vocal_agent.py`

Le flux vocal permet à un utilisateur d'interagir avec le système par téléphone à travers **Asterisk**, **Whisper**, **Ollama** et **Piper**.

1. Le service vocal est lancé avec un **compte de service** `vocal-agent` disposant du rôle `operator`.
2. L'appelant compose l'extension **2000** depuis un softphone tel que **Linphone** ou **Zoiper**.
3. **Asterisk** redirige l'appel vers l'application Stasis `asterisk-vocal-ai`.
4. `vocal_agent.py` reçoit l'événement `StasisStart` via le **WebSocket ARI**.
5. L'agent crée :
   - un **Bridge** ;
   - un canal **Snoop** permettant d'écouter l'appelant ;
   - un canal **External Media** permettant d'envoyer l'audio vers l'application via UDP.
6. Un message d'accueil est généré avec **Piper (TTS)** puis joué à l'appelant.
7. L'audio provenant de l'appelant est reçu via **UDP** au format `slin16`.
8. Lorsqu'un silence d'environ **1,2 seconde** est détecté, l'audio est envoyé à **Whisper** pour effectuer la transcription (**STT**).
9. Le texte transcrit est transmis au **LLM local (Ollama)**, qui analyse la demande et détermine l'outil MCP à utiliser.
10. Le token d'authentification est automatiquement **rafraîchi si nécessaire** grâce au `refresh_token`.
11. Le serveur MCP reçoit la requête, vérifie le **JWT**, applique le **RBAC**, puis exécute l'outil autorisé.
12. Le résultat de l'outil est transmis au LLM, qui génère une réponse textuelle.
13. La réponse est convertie en audio avec **Piper (TTS)** puis jouée dans le canal téléphonique via **ARI**.
14. L'appelant entend finalement la réponse vocale.

#### Schéma du flux

```text
                    Appel téléphonique
                           │
                           ▼
                  Softphone (Linphone/
                       Zoiper)
                           │
                           ▼
                       Asterisk
                           │
                           │ StasisStart
                           ▼
                  vocal_agent.py
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
          Bridge         Snoop      External Media
                                           │
                                           │ UDP / slin16
                                           ▼
                                      Whisper (STT)
                                           │
                                           │ Texte
                                           ▼
                                  Ollama + Qwen 2.5
                                           │
                                           │ Appel outil MCP
                                           ▼
                                     Serveur MCP
                                           │
                                  JWT + RBAC
                                           │
                                           ▼
                                      Outil MCP
                                           │
                                           ▼
                                       Asterisk
                                           │
                                           │ Résultat
                                           ▼
                                  Ollama + Qwen 2.5
                                           │
                                           │ Réponse textuelle
                                           ▼
                                      Piper (TTS)
                                           │
                                           │ Audio
                                           ▼
                                        ARI
                                           │
                                           ▼
                                      Asterisk
                                           │
                                           ▼
                                      Appelant
```

#### Résumé du pipeline vocal

```text
Voix
  │
  ▼
Asterisk
  │
  ▼
UDP / slin16
  │
  ▼
Whisper (STT)
  │
  ▼
Texte
  │
  ▼
Ollama + Qwen 2.5
  │
  ▼
Serveur MCP
  │
  ├──► JWT
  ├──► RBAC
  └──► Outil MCP
          │
          ▼
       Asterisk
          │
          ▼
     Résultat outil
          │
          ▼
Ollama + Qwen 2.5
          │
          ▼
      Piper (TTS)
          │
          ▼
       Asterisk
          │
          ▼
       Réponse vocale
```


## Description en deux lignes de chaque dossier et fichier

### Fichiers racine

- **`agent.py`**  
  Agent en ligne de commande ; l'utilisateur s'authentifie via Keycloak puis dialogue en français avec le LLM, qui appelle les outils MCP exposés par le serveur.

- **`vocal_agent.py`**  
  Agent vocal Speech-to-Speech ; reçoit les appels Asterisk, transcrit la voix (Whisper), interroge le LLM, exécute les outils MCP, puis synthétise la réponse vocale (Piper).

- **`server.py`**  
  Serveur MCP central basé sur FastMCP ; expose les 14 outils, vérifie le JWT à chaque appel et applique le contrôle d'accès par rôle (RBAC).

- **`requirements.txt`**  
  Liste des dépendances Python (FastMCP, faster-whisper, piper-tts, ollama, aiohttp, python-jose, etc.).

- **`run_server_with_token.sh`**  
  Script wrapper qui récupère un token Keycloak puis lance le serveur MCP avec ce token.

- **`run_vocal_with_token.sh`**  
  Script wrapper qui récupère un access token + refresh token puis lance l'agent vocal.

### Dossiers

#### `config/`

Centralise la configuration de l'application (variables d'environnement, logging).

- **`settings.py`**  
  Charge les variables depuis `.env` (URL ARI, identifiants, Keycloak, Ollama).

- **`logging_config.py`**  
  Configure le logging applicatif et le journal d'audit.

#### `security/`

Gère l'authentification et l'autorisation (Keycloak + JWT + RBAC).

- **`auth.py`**  
  Vérifie les JWT, extrait les rôles, fournit le décorateur `@require_roles` et le rafraîchissement du token.

- **`context.py`**  
  Stocke le contexte utilisateur courant (username, rôles, token) de manière thread-safe.

- **`keycloak_realm.json`**  
  Export du realm Keycloak contenant les rôles, le client et les utilisateurs.

#### `asterisk/`

Clients d'accès à Asterisk (ARI et CDR).

- **`ari_client.py`**  
  Client ARI pour les appels REST synchrones (outils MCP) et asynchrones (pipeline vocal).

- **`cdr_client.py`**  
  Client MySQL pour interroger la base CDR (historique des appels).

#### `tools/`

Définition des outils MCP exposés au LLM.

- **`supervision.py`**  
  Outils de lecture (`get_asterisk_info`, `list_active_channels`, `list_endpoints`, `get_extension_status`, `get_queue_stats`).

- **`analysis.py`**  
  Outils d'analyse (`get_cdr_report`, `analyze_call_quality` avec calcul MOS, `get_trunk_utilization`).

- **`control.py`**  
  Outils de pilotage (`originate_call`, `make_call`, `hangup_channel`, `redirect_call`, `spy_channel`).

#### `s2s/`

Pipeline Speech-to-Speech (voix → texte → IA → texte → voix).

- **`stt.py`**  
  Reconnaissance vocale via faster-whisper (modèle small, français) avec filtrage des hallucinations.

- **`tts.py`**  
  Synthèse vocale via Piper + ffmpeg (conversion en 8000 Hz mono pour Asterisk).

#### `models/`

Contient les fichiers du modèle Piper (`fr_FR-siwis-medium.onnx` et son JSON de configuration).

#### `logs/`

Contient le journal d'audit `audit.log` où sont tracées toutes les exécutions d'outils.

#### `tests/`

Contient les tests de charge et d'intégration.

- **`sipp_scenario.xml`**  
  Scénario SIPp simulant un appel entrant vers l'extension 2000.

- **`test_load.sh`**  
  Script de test progressif (10 → 50 canaux simultanés).

- **`analyze_sipp.py`**  
  Analyse des résultats SIPp (taux de succès, échecs).

#### `schemas/`

Destiné à contenir les schémas JSON des outils MCP (livrable du cahier des charges).

#### `venv/`

Environnement virtuel Python isolant les dépendances du projet.
