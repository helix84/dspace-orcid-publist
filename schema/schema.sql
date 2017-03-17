DROP TABLE IF EXISTS utb_orcid_client_apps;
CREATE TABLE public.utb_orcid_client_apps (
    env character varying(10) NOT NULL,
    api character varying(6),
    client_id character varying(20),
    client_secret character varying(36) NOT NULL,
    redirect_uri character varying(1000) NOT NULL
) WITH (oids = false);

-- example values
INSERT INTO utb_orcid_client_apps (env, api, client_id, client_secret, redirect_uri) VALUES
('sandbox',	'public',	'APP-A1B2C3D4E5F6G7H8',	'80f0bc38-c218-435b-a1bc-3dd7383e255c',	'https://dspace.example.com/path/to/auth.py');
('sandbox',	'member',	'APP-XA1B2C3D4E5F6G7H',	'2110e916-76c2-4531-b22e-14212a77a8f7',	'https://dspace.example.com/path/to/auth.py');
('production',	'public',	'APP-XYA1B2C3D4E5F6G7',	'f23b8089-ee23-4852-b182-0acea58c9b80',	'https://dspace.example.com/path/to/auth.py');
('production',	'member',	'APP-XYZA1B2C3D4E5F6G',	'785f9d7a-0e10-488d-b4ac-41161d36eeb5',	'https://dspace.example.com/path/to/auth.py');


DROP TABLE IF EXISTS utb_orcid_tokens;
CREATE TABLE public.utb_orcid_tokens (
    env character varying(10) NOT NULL,
    client_id character varying(20),
    orcid character varying(19),
    scope character varying(18),
    token character varying(36) NOT NULL,
    expiry timestamp NOT NULL,
    refresh_token character varying(36) NOT NULL,
    CONSTRAINT utb_orcid_tokens_pk PRIMARY KEY (client_id, orcid, scope)
) WITH (oids = false);

-- example values
INSERT INTO utb_orcid_tokens (env, client_id, orcid, scope, token, expiry, refresh_token) VALUES
('sandbox',	'APP-XA1B2C3D4E5F6G7H',	'0000-0012-3456-789X',	'/read-limited',	'f263adbc-e88c-4dc2-8540-9fbf8763a155',	'2037-03-06 10:25:47.701833',	'228a835d-72b8-44b2-800c-fe55ec3f05de');
('production',	'APP-XYZA1B2C3D4E5F6G',	'0000-0012-3456-789X',	'/activities/update',	'02cfcc94-86a1-42c2-bfb1-178c4684561d',	'2037-03-08 13:03:04.378068',	'dd156ca8-38d1-431f-8464-eaaf0fd6e461'),


-- we store many other columns here, but only these are relevant to the ORCID client app
DROP TABLE IF EXISTS utb_authors;
CREATE TABLE public.utb_authors (
    "displayName" character varying(1024) NOT NULL,
    "ORCID" character varying(19) NOT NULL
) WITH (oids = false);

-- example values
INSERT INTO utb_authors ("displayName", "ORCID") VALUES
('Surname, Name',	'0000-0012-3456-789X');
