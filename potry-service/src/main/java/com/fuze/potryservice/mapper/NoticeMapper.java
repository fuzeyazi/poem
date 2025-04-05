package com.fuze.potryservice.mapper;

import com.fuze.dto.NoticeDto;
import com.fuze.entity.Notice;
import com.fuze.enumeration.OperationType;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface NoticeMapper {
    @Insert("insert into Poem.notice(name,contents,createtime) values(#{name},#{contents},#{createtime})")
    void add(Notice notice);
@Delete("delete from Poem.notice where id=#{id}")
    void delete(Long id);
@Select("select * from Poem.notice")
    Page<Notice> GetNoticeByPage();

    void update(Notice notice);
@Select("select * from Poem.notice")
    List<NoticeDto> getNotice();
}
