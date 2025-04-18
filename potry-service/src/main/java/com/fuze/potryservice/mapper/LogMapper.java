package com.fuze.potryservice.mapper;

import com.fuze.entity.Log;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface LogMapper {
    @Select("select * from Poem.log")
    Page<Log> GetLog();
@Insert("insert into Poem.log(title,time) values(#{title},#{time})")
    void addLog(String title, String time);
@Delete("delete from Poem.log where id=#{id}")
    void deleteLog(Long id);
}
