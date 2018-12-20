#ifndef TEST_A_H
#define TEST_A_H
namespace test
{
class A
{
public:
    A();
    ~A();
    void funaa();
    void funaa(int i);
    void funab();
    virtual void funac();
public:
    int m_ai;
    static int s_i;
private:
    float m_af;
protected:
    float m_af2;
  
};
}
#endif //TEST_A_H