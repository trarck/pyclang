/**
 * just a test a B class
 */
#ifndef TEST_B_
#define TEST_B_

#include "a.h"
class B
{
public:
    B();
    ~B();
    void funba();
    void funbb();
    void funbc()
    {
        m_bi=55;
    }
private:
    int m_bi;
    float m_bf;
};
#endif //TEST_B_