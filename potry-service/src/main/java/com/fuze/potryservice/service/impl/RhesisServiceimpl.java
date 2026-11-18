package com.fuze.potryservice.service.impl;

import com.fuze.entity.Rhesis;
import com.fuze.potryservice.config.RandomIdPool;
import com.fuze.potryservice.mapper.RhesisMapper;
import com.fuze.potryservice.service.RhesisService;
import com.fuze.result.PageResult;
import com.fuze.vo.RhesisDataVo;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;

@Service
public class RhesisServiceimpl implements RhesisService {
    @Autowired
    private RhesisMapper rhesisMapper;

    @Autowired
    private RandomIdPool randomIdPool;

    @Override
    public Integer getcount() {
        return rhesisMapper.getcount();
    }

    @Override
    public List<String> GetAllRhesisName() {
        return rhesisMapper.GetAllRhesisName();
    }

    @Override
    public Rhesis GetContentById(Integer id) {
        return rhesisMapper.GetContentById(id);
    }

    @Override
    public RhesisDataVo GetVeryGoodRhesis() {
        RhesisDataVo picked = null;
        for (int i = 0; i < 4; i++) {   // 出处为挽词/悼亡类时重抽,与今日推荐诗同策略
            List<RhesisDataVo> list = getRhesisByRandom(1);
            if (list.isEmpty()) {
                return rhesisMapper.GetVeryGoodPoem();
            }
            picked = list.get(0);
            String fromm = picked == null ? null : picked.getFromm();
            boolean elegiac = fromm != null && (fromm.contains("挽") || fromm.contains("悼")
                    || fromm.contains("祭") || fromm.contains("墓") || fromm.contains("葬"));
            if (!elegiac) {
                return picked;
            }
        }
        return picked;
    }

    @Override
    public List<RhesisDataVo> GetRhesisByKey(String keyword) {
        return rhesisMapper.GetRhesisByKey(keyword);
    }

    @Override
    public List<RhesisDataVo> GetRhesisDateRondom() {
        List<RhesisDataVo> list = getRhesisByRandom(10);
        return list.isEmpty() ? rhesisMapper.GetRhesisDateRondom() : list;
    }

    /** Redis随机id池(SRANDMEMBER)+主键IN回表, 替代rhesis万行表的ORDER BY RAND() filesort */
    private List<RhesisDataVo> getRhesisByRandom(int n) {
        List<Integer> ids = randomIdPool.randomIds(RandomIdPool.RHESIS_POOL, n, rhesisMapper::GetAllRhesisIds);
        return ids.isEmpty() ? Collections.emptyList() : rhesisMapper.GetRhesisByIds(ids);
    }

    @Override
    public PageResult GetRhesisPage(Integer pageNum, Integer pageSize) {
        // 原PageHelper+ORDER BY RAND()分页每次重洗页序无意义; 改为随机pageSize条+真实总数
        List<RhesisDataVo> records = getRhesisByRandom(pageSize);
        if (records.isEmpty()) {
            records = rhesisMapper.GetRhesisDateRondom();
        }
        return new PageResult(rhesisMapper.getcount(), records);

    }
}
