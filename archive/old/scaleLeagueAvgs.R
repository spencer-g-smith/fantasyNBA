source("~/Documents/my_functions.R")


q <- "select * from season_averages_22"
league22 <- query_mySQL_local(q)

league22 <- league22[league22$games_played>20,]
head(league22)

#### UPDATE Claimed Player Scaled Stats ####
scale_df <- league22[!(names(league22) %in% c("games_played", "season", "min"))]

stats <- c("fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "turnover", "pf", "pts", "fg_pct", "fg3_pct", "ft_pct")
for(n in names(scale_df[,stats])){ 
  print(n)
  scale_df[paste(n, "sc", sep ="_")] <- scale(scale_df[n])
}




######## TODO: Left off here ###

categories <- c('fg3m_sc', 'reb_sc', 'ast_sc', 'stl_sc', 'blk_sc', 'pts_sc', 'ft_pct_sc')
scale_df$scaleSum <- rowSums(scale_df[,categories])


scale_df[order(scale_df$scaleSum, decreasing = T), c('first_name', 'last_name','player_id', 'scaleSum')]

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = 'Soccer0066',
                 host='localhost',
                 db = 'nba')
dbWriteTable(con, value = scale_df, name = "leagueScaledAvgs22", rownames= F, overwrite = T )

#### UPDATE Claimed Player Scaled Stats ####




copy_paste(scale_df)