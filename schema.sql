-- =====================================================
-- Schema del database — Mini gestionale InVibe
-- Database: SQLite
-- Importi salvati in CENTESIMI (INTEGER): 350,00 € = 35000
-- =====================================================

-- Pratica: un viaggio prenotato, con un solo IBAN virtuale
CREATE TABLE IF NOT EXISTS pratiche (
    practice_id   TEXT PRIMARY KEY,              -- es. CASE-1001
    virtual_iban  TEXT NOT NULL UNIQUE,          -- un IBAN per pratica, non per partecipante
    destinazione  TEXT NOT NULL,
    data_inizio   TEXT NOT NULL,                 -- date in formato ISO: AAAA-MM-GG
    data_fine     TEXT NOT NULL
);

-- Partecipante: appartiene a una sola pratica
CREATE TABLE IF NOT EXISTS partecipanti (
    participant_id  TEXT PRIMARY KEY,            -- es. P-001
    practice_id     TEXT NOT NULL REFERENCES pratiche(practice_id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    cognome         TEXT NOT NULL
);

-- Servizio acquistato da un partecipante (pacchetto, navetta, ...)
CREATE TABLE IF NOT EXISTS servizi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id  TEXT NOT NULL REFERENCES partecipanti(participant_id) ON DELETE CASCADE,
    codice          TEXT NOT NULL,               -- es. PACKAGE, NAVETTA
    nome            TEXT NOT NULL,
    importo_cent    INTEGER NOT NULL CHECK (importo_cent >= 0)
);

-- Rata di un partecipante: 3 per partecipante, con importo e scadenza
CREATE TABLE IF NOT EXISTS rate (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id  TEXT NOT NULL REFERENCES partecipanti(participant_id) ON DELETE CASCADE,
    numero          INTEGER NOT NULL CHECK (numero > 0),
    percentuale     INTEGER NOT NULL CHECK (percentuale BETWEEN 0 AND 100),
    scadenza        TEXT NOT NULL,
    importo_cent    INTEGER NOT NULL CHECK (importo_cent >= 0),
    UNIQUE (participant_id, numero)              -- niente due "rata 1" per lo stesso partecipante
);

-- Pagamento: un bonifico importato dal file dei movimenti bancari
CREATE TABLE IF NOT EXISTS pagamenti (
    id_movimento    TEXT PRIMARY KEY,            -- es. TX-001: impedisce di importare due volte lo stesso bonifico
    data            TEXT NOT NULL,
    iban_virtuale   TEXT NOT NULL,
    importo_cent    INTEGER NOT NULL CHECK (importo_cent > 0),
    causale         TEXT NOT NULL,
    practice_id     TEXT NOT NULL REFERENCES pratiche(practice_id),
    participant_id  TEXT NOT NULL REFERENCES partecipanti(participant_id)
);

-- Imputazione: quanta parte di un pagamento è andata su quale rata
-- (un bonifico può coprire più rate, una rata può essere pagata con più bonifici)
CREATE TABLE IF NOT EXISTS imputazioni (
    id_movimento    TEXT NOT NULL REFERENCES pagamenti(id_movimento),
    rata_id         INTEGER NOT NULL REFERENCES rate(id),
    importo_cent    INTEGER NOT NULL CHECK (importo_cent > 0),
    PRIMARY KEY (id_movimento, rata_id)
);

-- Utente del gestionale (operatore InVibe)
-- Descritto per completezza del modello: nel prototipo non sono previsti login e permessi
CREATE TABLE IF NOT EXISTS utenti (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome    TEXT NOT NULL,
    email   TEXT NOT NULL UNIQUE,
    ruolo   TEXT NOT NULL CHECK (ruolo IN ('admin', 'operatore'))
);