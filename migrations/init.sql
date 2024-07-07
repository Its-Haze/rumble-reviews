CREATE TABLE IF NOT EXISTS movie_reviews (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    user_name TEXT NOT NULL,
    movie_id TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    review_score INT NOT NULL,
    review_time TIMESTAMP NOT NULL,
    PRIMARY KEY (guild_id, user_id, movie_id)
);
