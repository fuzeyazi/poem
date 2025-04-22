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
    @Select("select * from poem.log")
    Page<Log> GetLog();
@Insert("insert into poem.log(title,time) values(#{title},#{time})")
    void addLog(String title, String time);
@Delete("delete from poem.log where id=#{id}")
    void deleteLog(Long id);
}
