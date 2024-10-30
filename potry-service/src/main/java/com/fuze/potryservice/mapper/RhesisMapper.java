package com.fuze.potryservice.mapper;

import com.fuze.entity.Rhesis;
import com.fuze.vo.RhesisDataVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface RhesisMapper {



    @Select("select count(*) from poem.rhesis")
        Integer getcount();
@Select("SELECT name from poem.rhesis")
    List<String> GetAllRhesisName();
@Select("select * from poem.rhesis where id=#{id}")
    Rhesis GetContentById(Integer id);
@Select("select id,name,fromm from poem.rhesis order by rand() limit 1")
    RhesisDataVo GetVeryGoodPoem();
    @Select("select id,name,fromm from poem.rhesis where name like concat('%', #{keyword}, '%')")
    List<RhesisDataVo> GetRhesisByKey(String keyword);
@Select("select id,name,fromm from poem.rhesis order by rand() limit 10")
    List<RhesisDataVo> GetRhesisDateRondom();
}
