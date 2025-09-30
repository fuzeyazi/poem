package com.fuze.potryservice.controller.user;

import com.fuze.result.Result;
import io.swagger.annotations.Api;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;

@RestController
@RequestMapping("/build")
@Api(tags ="重建sql")
@Slf4j
public class buildSqlController {
    static int kk=0;
@PostMapping("bulid")
    private Result<String> buildSql() throws SQLException {
    String dbUrl = "jdbc:mysql://120.27.234.36:3306";
    String username = "root";
    String password = "123456";

    try {
        Connection conn = DriverManager.getConnection(dbUrl, username, password);
        Statement st = conn.createStatement();
        st.execute("DROP DATABASE IF EXISTS poem;");
        st.execute("DROP DATABASE IF EXISTS Poem;");
        st.execute("create schema poem collate utf8mb4_0900_ai_ci;");
        st.execute("USE poem;");
        if(kk==0){
            ScriptUtils.executeSqlScript(conn, new ClassPathResource("sql/poemmax.sql"));
        }else{
        ScriptUtils.executeSqlScript(conn, new ClassPathResource("sql/poemmax"+kk+".sql"));}
    }catch (SQLException e){
        Connection conn = DriverManager.getConnection(dbUrl, username, password);
        Statement st = conn.createStatement();
        st.execute("DROP DATABASE IF EXISTS poem;");
        st.execute("create schema poem collate utf8mb4_0900_ai_ci;");
        st.execute("USE poem;");
        ScriptUtils.executeSqlScript(conn, new ClassPathResource("sql/poemmax.sql"));
        log.error("连接失败,{}",e.getMessage());
        return Result.error("连接失败");
    }
    return Result.success("重建成功");
    }


}
