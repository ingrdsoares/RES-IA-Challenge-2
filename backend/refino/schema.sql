-- Contrato PostgreSQL da migração inicial; não aplicado automaticamente.
CREATE SCHEMA refino;
CREATE TABLE refino.politica (
    sha256 char(64) PRIMARY KEY,
    perfil text NOT NULL,
    definicao jsonb NOT NULL
);
CREATE TABLE refino.documento (
    id char(64) PRIMARY KEY,
    chave_origem text NOT NULL UNIQUE,
    titulos jsonb NOT NULL,
    naturezas jsonb NOT NULL,
    representacao_preferida char(64),
    criterio_representacao text NOT NULL
);
CREATE TABLE refino.conteudo (
    id char(64) PRIMARY KEY,
    arquivo text NOT NULL,
    bytes bigint NOT NULL CHECK (bytes >= 0),
    normalizacao text NOT NULL
);
CREATE TABLE refino.versao (
    id char(64) PRIMARY KEY,
    documento_id char(64) NOT NULL REFERENCES refino.documento(id),
    conteudo_id char(64) REFERENCES refino.conteudo(id),
    hashes_originais jsonb NOT NULL,
    qualidade jsonb NOT NULL,
    revisao_semantica text NOT NULL DEFAULT 'pendente',
    UNIQUE (documento_id, id)
);
ALTER TABLE refino.documento ADD CONSTRAINT documento_representacao_fk
    FOREIGN KEY (id, representacao_preferida) REFERENCES refino.versao(documento_id, id)
    DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE refino.ocorrencia (
    id char(64) PRIMARY KEY,
    versao_id char(64) NOT NULL REFERENCES refino.versao(id),
    metadados_ref text NOT NULL,
    hash_metadados char(64) NOT NULL,
    markdown_ref text,
    hash_markdown char(64),
    source_url text NOT NULL,
    coletado_em text,
    originais jsonb NOT NULL,
    visoes jsonb NOT NULL,
    vigencia text NOT NULL DEFAULT 'nao_verificada',
    qualidade jsonb NOT NULL,
    erros jsonb NOT NULL,
    UNIQUE (id, versao_id)
);
CREATE TABLE refino.classificacao (
    ocorrencia_id char(64) NOT NULL REFERENCES refino.ocorrencia(id),
    politica_sha256 char(64) NOT NULL REFERENCES refino.politica(sha256),
    categoria text NOT NULL CHECK (categoria IN (
        'nucleo','complementar','historico','revisao','evidencia','dados_estruturados')),
    motivos jsonb NOT NULL,
    PRIMARY KEY (ocorrencia_id, politica_sha256)
);
CREATE TABLE refino.dataset (
    id char(64) PRIMARY KEY,
    documento_id char(64) NOT NULL REFERENCES refino.documento(id),
    versao_id char(64) NOT NULL REFERENCES refino.versao(id),
    competencia text,
    registros bigint,
    artefatos jsonb NOT NULL,
    metadados_ref text NOT NULL,
    FOREIGN KEY (id, versao_id) REFERENCES refino.ocorrencia(id, versao_id),
    FOREIGN KEY (documento_id, versao_id) REFERENCES refino.versao(documento_id, id)
);
CREATE TABLE refino.relacao (
    documento_id char(64) NOT NULL REFERENCES refino.documento(id),
    relacionado_id char(64) NOT NULL REFERENCES refino.documento(id),
    tipo text NOT NULL,
    evidencia text NOT NULL,
    PRIMARY KEY (documento_id, relacionado_id, tipo)
);
CREATE INDEX versao_documento_idx ON refino.versao(documento_id);
CREATE INDEX ocorrencia_versao_idx ON refino.ocorrencia(versao_id);
CREATE INDEX classificacao_categoria_idx ON refino.classificacao(politica_sha256, categoria);
