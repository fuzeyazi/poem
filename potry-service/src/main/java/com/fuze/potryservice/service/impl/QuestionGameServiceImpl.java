package com.fuze.potryservice.service.impl;

import com.fuze.potryservice.mapper.QuestionGameMapper;
import com.fuze.potryservice.service.QuestionGameService;
import com.fuze.vo.GameRankVo;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Slf4j
@Service
public class QuestionGameServiceImpl implements QuestionGameService {
    @Autowired
    private QuestionGameMapper questionGameMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    private static final String RANK_ZSET_KEY = "gamerank:zset";
    private static final String RANK_NAMES_KEY = "gamerank:names";

    /** Redis 5.x 无 ZADD GT,用 Lua 保证"仅更高分才覆盖+补记用户名"的原子性 */
    private static final DefaultRedisScript<Long> HIGHER_SCORE_SCRIPT = new DefaultRedisScript<>(
            "local c = redis.call('ZSCORE', KEYS[1], ARGV[1]) " +
            "if (not c) or (tonumber(ARGV[2]) > tonumber(c)) then " +
            "  redis.call('ZADD', KEYS[1], ARGV[2], ARGV[1]) " +
            "  redis.call('HSET', KEYS[2], ARGV[1], ARGV[3]) " +
            "  return 1 end return 0", Long.class);

    @Override
    public void addQuestion(String s) {
        questionGameMapper.addQuestion(s);
    }

    @Override
    public String getQuestion() {
        return questionGameMapper.getquestion();
    }

    @Override
    public void deleteQuestion() {
        questionGameMapper.deleteQuestion();
    }

    @Override
    public void addsum(int sum, Integer userId,String name) {
        questionGameMapper.addsum(sum, userId,name);
        //双写Redis ZSet(仅更高分覆盖,原子Lua);MySQL保留全量答题记录作审计与重建来源
        try {
            stringRedisTemplate.execute(HIGHER_SCORE_SCRIPT,
                    List.of(RANK_ZSET_KEY, RANK_NAMES_KEY),
                    String.valueOf(userId), String.valueOf(sum), name);
        } catch (Exception e) {
            log.warn("排行榜ZSet更新失败,不影响主流程", e);
        }
    }

    @Override
    public String getusername(Integer userId) {
        return questionGameMapper.getusename(userId);
    }

    @Override
    public List<GameRankVo> getRank() {
        try {
            rebuildIfEmpty();
            Set<String> topSet = stringRedisTemplate.opsForZSet().reverseRange(RANK_ZSET_KEY, 0, 19);
            if (topSet != null && !topSet.isEmpty()) {
                List<String> top = new ArrayList<>(topSet);
                List<Object> names = stringRedisTemplate.opsForHash()
                        .multiGet(RANK_NAMES_KEY, new ArrayList<Object>(top));
                List<GameRankVo> result = new ArrayList<>(top.size());
                for (int i = 0; i < top.size(); i++) {
                    GameRankVo vo = new GameRankVo();
                    vo.setUserid(top.get(i));
                    Object name = names != null && i < names.size() ? names.get(i) : null;
                    vo.setUsename(name != null ? name.toString() : "");
                    result.add(vo);
                }
                //分数单独补(带分数版返回结构解析繁琐,数量仅20,开销可忽略)
                for (GameRankVo vo : result) {
                    Double score = stringRedisTemplate.opsForZSet().score(RANK_ZSET_KEY, vo.getUserid());
                    vo.setGrand(score == null ? "0" : String.valueOf(score.longValue()));
                }
                return result;
            }
        } catch (Exception e) {
            log.warn("排行榜ZSet不可用,降级MySQL查询", e);
        }
        return questionGameMapper.getRank();
    }

    /** ZSet为空(首次访问/Redis被清)时,从MySQL按用户最高分聚合重建 */
    private void rebuildIfEmpty() {
        Long size = stringRedisTemplate.opsForZSet().zCard(RANK_ZSET_KEY);
        if (size != null && size > 0) {
            return;
        }
        List<GameRankVo> all = questionGameMapper.getRankAllForRebuild();
        if (all == null || all.isEmpty()) {
            return;
        }
        Map<String, String> names = new HashMap<>(all.size());
        for (GameRankVo vo : all) {
            names.put(vo.getUserid(), vo.getUsename());
        }
        stringRedisTemplate.opsForHash().putAll(RANK_NAMES_KEY, names);
        ZSetOperations<String, String> zops = stringRedisTemplate.opsForZSet();
        for (GameRankVo vo : all) {
            zops.add(RANK_ZSET_KEY, vo.getUserid(), Double.parseDouble(vo.getGrand()));
        }
        log.info("排行榜ZSet重建完成,用户数: {}", all.size());
    }

    @Override
    public PageInfo<GameRankVo> selectPageVO(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum,pageSize);
        List<GameRankVo> list = questionGameMapper.getalluser();
        return new PageInfo<>(list);
    }

    @Override
    public void delete(Integer id) {
        questionGameMapper.delete(id);
    }

    @Override
    public List<GameRankVo> getuserRank(Integer userid) {
        return questionGameMapper.getuserRanl(userid);
    }
}
