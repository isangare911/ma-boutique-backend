# 🔒 Sécurité — Ma Boutique Backend

Document de référence des mesures de sécurité de l'application Ma Boutique.
**À mettre à jour à chaque changement impactant la sécurité.**

Dernière mise à jour : 2026-10-06

---

## 📋 Table des matières

1. [Résumé](#résumé)
2. [Variables d'environnement](#variables-denvironnement)
3. [Authentification & JWT](#authentification--jwt)
4. [Throttling (rate limiting)](#throttling-rate-limiting)
5. [Multi-tenant (isolation par boutique)](#multi-tenant-isolation-par-boutique)
6. [Calculs serveur (anti-fraude)](#calculs-serveur-anti-fraude)
7. [Mots de passe](#mots-de-passe)
8. [Sync (offline-first)](#sync-offline-first)
9. [Headers HTTP & HTTPS](#headers-http--https)
10. [Logs & audit](#logs--audit)
11. [Endpoints sensibles](#endpoints-sensibles)
12. [Failles corrigées (historique)](#failles-corrigées-historique)
13. [Checklist avant déploiement](#checklist-avant-déploiement)
14. [Tests automatisés](#tests-automatisés)

---

## Résumé

L'application a été auditée et corrigée pour fermer les failles suivantes :

- 🔴 **Escalade de privilèges** (route d'activation d'abonnement supprimée)
- 🔴 **Login sans mot de passe** (routes OTP désactivées)
- 🔴 **Fuite cross-tenant** (isolation stricte par `shop_id`)
- 🔴 **Fraude sur les ventes** (montants calculés côté serveur)
- 🔴 **Double comptage crédit** (recalcul via SUM des paiements)
- 🔴 **Stock non décrémenté** (décrémentation + restauration côté serveur)
- 🔴 **Brute force login/register** (throttling)
- 🔴 **JWT longue durée** (30 min + refresh + blacklist)
- 🔴 **Mots de passe faibles** (8 caractères + validateurs Django)

---

## Variables d'environnement

### Développement (`.env`)

```env
SECRET_KEY=<clé_locale_50+_chars_différente_de_la_prod>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2
CORS_ALLOWED_ORIGINS=
CSRF_TRUSTED_ORIGINS=
DATABASE_URL=postgresql://user:pass@localhost:5432/ma_boutique
REDIS_URL=redis://localhost:6379/0
ORANGE_CLIENT_ID=
ORANGE_CLIENT_SECRET=
ORANGE_SENDER_NUMBER=
ORANGE_SENDER_NAME=MaBoutique
OTP_EXPIRY_SECONDS=300