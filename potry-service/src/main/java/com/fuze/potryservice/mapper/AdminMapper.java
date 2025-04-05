package com.fuze.potryservice.mapper;

import com.fuze.dto.AdminLoginDto;
import com.fuze.dto.PotryDTO;
import com.fuze.entity.Admin;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.springframework.beans.factory.annotation.Value;

import java.util.List;

@Mapper
public interface AdminMapper {
@Select("select * from poem.admin where username=#{username}")
Admin getByUsername(String username);
    @Insert("INSERT INTO poem.potry(title, dynasty, writer, type, content) " +
            "VALUES (#{title}, #{dynasty}, #{writer}, #{type}, #{content})")
    void insert(PotryDTO potryDTO);
@Delete("delete from poem.potry where id in (#{ids})")
    void delete(Long id);
@Insert("INSERT INTO poem.admin(username, password, email, phone,status,created_at,updated_at) " + "VALUES(#{username}, #{password}, #{email}, #{phone},#{status},#{createdAt},#{updatedAt})")
    void register(Admin admin);
@Select("select * from poem.admin where email=#{email}")
    Boolean getByemail(String email);

    void update(PotryDTO potryDTO);
}
