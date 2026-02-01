# 🎮 Deg Bot - Bot Discord de Coaching League of Legends

Bot Discord complet pour gérer les réservations de coaching, l'intégration avec Google Calendar, et la gestion des événements pour Deg Coaching.

## ✨ Fonctionnalités

### 🎫 Système de Tickets et Réservation (✅ Implémenté)
- Création automatique de tickets privés
- Sélection du type de coaching (Gratuit/Payant)
- Interface de sélection de date et d'heure
- Intégration avec Google Calendar
- Confirmation automatique
- Notifications pour les coachs

### 📅 Intégration Google Calendar (✅ Implémenté)
- Lecture des disponibilités en temps réel
- Création automatique d'événements
- Gestion des créneaux horaires (9h-20h)
- Support de plusieurs durées de session

### 🔔 Rappels Automatiques (🚧 À venir)
- Rappel 24h avant la session
- Rappel 1h avant la session
- Rappels personnalisables

### 📊 Événements Discord (🚧 À venir)
- Création d'événements de groupe
- Système d'inscription
- Annonces automatiques

### ⭐ Système de Feedback (🚧 À venir)
- Collecte automatique après chaque session
- Notation 1-5 étoiles
- Partage optionnel dans #feedback

### 📈 Dashboard et Statistiques (🚧 À venir)
- Statistiques de coaching
- Historique des clients
- Notes sur les élèves

## 🚀 Installation

### Prérequis

- Python 3.11 ou supérieur
- Un serveur Discord avec permissions administrateur
- Un compte Google avec accès à Google Calendar API
- Git (optionnel)

### 1. Cloner le projet

```bash
git clone <votre-repo>
cd deg-bot
```

### 2. Créer un environnement virtuel

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configuration Discord

1. Créez une application Discord sur [Discord Developer Portal](https://discord.com/developers/applications)
2. Créez un bot et récupérez le token
3. Activez les intents suivants:
   - Server Members Intent
   - Message Content Intent
4. Invitez le bot sur votre serveur avec les permissions:
   - Manage Channels
   - Manage Roles
   - Send Messages
   - Embed Links
   - Manage Messages
   - Read Message History
   - Add Reactions

### 5. Configuration Google Calendar

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un nouveau projet
3. Activez l'API Google Calendar
4. Créez un compte de service:
   - IAM & Admin > Service Accounts
   - Create Service Account
   - Téléchargez la clé JSON
5. Partagez votre Google Calendar avec l'email du compte de service
6. Placez le fichier JSON dans le dossier du projet et nommez-le `credentials.json`

### 6. Configuration du serveur Discord

1. Créez les rôles suivants:
   - `Coach` (pour les coachs)
   - `Élève` (pour les élèves)

2. Créez les salons suivants:
   - Une catégorie `TICKETS` (pour les tickets)
   - Un salon `#annonces` (pour les annonces d'événements)
   - Un salon `#feedback` (pour les feedbacks publics)
   - Un salon `#logs` (pour les logs du bot)

3. Récupérez les IDs:
   - Activez le mode développeur dans Discord (Paramètres > Avancés > Mode développeur)
   - Faites clic droit sur les rôles/salons et copiez les IDs

### 7. Configuration des variables d'environnement

Copiez le fichier `.env.example` vers `.env` et remplissez les valeurs:

```bash
cp .env.example .env
```

Éditez `.env` avec vos valeurs:

```env
# Discord Configuration
DISCORD_TOKEN=votre_token_discord
GUILD_ID=id_de_votre_serveur
COACH_ROLE_ID=id_du_role_coach
STUDENT_ROLE_ID=id_du_role_eleve
TICKET_CATEGORY_ID=id_de_la_categorie_tickets
ANNOUNCEMENT_CHANNEL_ID=id_du_salon_annonces
FEEDBACK_CHANNEL_ID=id_du_salon_feedback
LOG_CHANNEL_ID=id_du_salon_logs

# Google Calendar Configuration
GOOGLE_CALENDAR_ID=votre_calendar_id@group.calendar.google.com
GOOGLE_CREDENTIALS_PATH=./credentials.json

# Bot Settings
BOOKING_SLOT_DURATION=60
TIMEZONE=Europe/Paris
FREE_COACHING_DURATION=60
PAID_COACHING_DURATION=60
```

### 8. Lancer le bot

```bash
python bot.py
```

Si tout est bien configuré, vous devriez voir:

```
✅ Base de données initialisée
✅ Cog chargé: cogs.tickets
--------------------------------------------------
Bot connecté en tant que: Deg Bot (ID: ...)
--------------------------------------------------
Bot prêt! 🚀
```

## 📖 Utilisation

### Configuration initiale

1. Lancez la commande `/setup-booking` dans le salon de votre choix
2. Le bot créera un message avec un bouton "Réserver un Coaching"
3. Les utilisateurs pourront cliquer sur ce bouton pour démarrer une réservation

### Commandes disponibles

#### Pour les administrateurs/coachs:
- `/setup-booking` - Créer le message de réservation
- `/ticket close` - Fermer le ticket actuel
- `/ticket add @user` - Ajouter un utilisateur au ticket

#### Pour tous les utilisateurs:
- Bouton "Réserver un Coaching" - Démarrer une réservation

## 🏗️ Architecture

```
deg-bot/
├── bot.py                    # Point d'entrée principal
├── config.py                 # Configuration
├── requirements.txt          # Dépendances Python
├── .env                      # Variables d'environnement (à créer)
├── credentials.json          # Credentials Google (à créer)
├── database/
│   ├── models.py             # Modèles SQLAlchemy
│   └── db.py                 # Connexion DB
├── cogs/
│   └── tickets.py            # Système de tickets
├── utils/
│   ├── embeds.py             # Embeds Discord
│   ├── permissions.py        # Gestion des permissions
│   └── google_calendar.py    # API Google Calendar
└── views/
    ├── booking_views.py      # Interfaces de réservation
    ├── feedback_views.py     # Interface de feedback
    └── calendar_views.py     # Navigation calendrier
```

## 🔧 Personnalisation

### Modifier les horaires de disponibilité

Dans [utils/google_calendar.py](utils/google_calendar.py#L60), modifiez les heures:

```python
# Actuellement: 9h-20h
if current_time.hour < 9 or current_time.hour >= 20:
    # Modifier ces valeurs
```

### Modifier les durées de coaching

Dans [.env](.env):

```env
FREE_COACHING_DURATION=60  # En minutes
PAID_COACHING_DURATION=60  # En minutes
```

### Modifier les couleurs des embeds

Dans [config.py](config.py):

```python
BOT_COLOR = 0x5865F2      # Couleur principale
SUCCESS_COLOR = 0x57F287  # Couleur de succès
ERROR_COLOR = 0xED4245    # Couleur d'erreur
```

## 🐛 Dépannage

### Le bot ne démarre pas

- Vérifiez que toutes les variables d'environnement sont définies
- Vérifiez que le token Discord est valide
- Vérifiez que les permissions du bot sont correctes

### Les réservations ne fonctionnent pas

- Vérifiez que `credentials.json` existe
- Vérifiez que le calendrier est partagé avec le compte de service
- Vérifiez les logs pour les erreurs d'API Google

### Les tickets ne se créent pas

- Vérifiez que `TICKET_CATEGORY_ID` est correct
- Vérifiez que le bot a la permission "Manage Channels"
- Vérifiez que la catégorie n'a pas atteint la limite de 50 salons

## 📝 Base de données

Le bot utilise SQLite avec SQLAlchemy. La base de données est créée automatiquement au premier lancement dans `deg_bot.db`.

### Tables:

- `clients` - Informations sur les clients
- `bookings` - Réservations de coaching
- `feedbacks` - Feedbacks des clients
- `notes` - Notes des coachs sur les clients
- `events` - Événements Discord
- `event_participants` - Participants aux événements

## 🚧 Fonctionnalités à venir

- [ ] Système de rappels automatiques (APScheduler)
- [ ] Gestion des événements de groupe
- [ ] Système de feedback post-session
- [ ] Dashboard de statistiques
- [ ] Commandes de gestion avancées
- [ ] Export des données en CSV
- [ ] Intégration avec système de paiement

## 🤝 Contribution

Les contributions sont les bienvenues! N'hésitez pas à ouvrir une issue ou une pull request.

## 📄 Licence

Ce projet est privé et destiné à un usage personnel pour Deg Coaching.

## 💬 Support

Pour toute question ou problème, contactez l'administrateur du serveur Discord.

---

Développé avec ❤️ pour Deg Coaching
